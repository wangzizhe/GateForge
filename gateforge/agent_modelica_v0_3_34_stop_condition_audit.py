from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_34_common import (
    DEFAULT_FAMILY_LEDGER_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0317_GENERATION_CENSUS_PATH,
    DEFAULT_V0317_ONE_STEP_REPAIR_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    second_residual_stage_count,
    tier_stage_count,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_34_family_ledger import build_v0334_family_ledger


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stop_condition_audit"


def build_v0334_stop_condition_audit(
    *,
    family_ledger_path: str = str(DEFAULT_FAMILY_LEDGER_OUT_DIR / "summary.json"),
    generation_census_path: str = str(DEFAULT_V0317_GENERATION_CENSUS_PATH),
    one_step_repair_path: str = str(DEFAULT_V0317_ONE_STEP_REPAIR_PATH),
    out_dir: str = str(DEFAULT_STOP_AUDIT_OUT_DIR),
) -> dict:
    if not Path(family_ledger_path).exists():
        build_v0334_family_ledger(out_dir=str(Path(family_ledger_path).parent))

    ledger = load_json(family_ledger_path)
    generation = load_json(generation_census_path)
    one_step = load_json(one_step_repair_path)

    families = {str(row.get("family_id")): row for row in (ledger.get("families") or []) if isinstance(row, dict)}
    local_interface = families.get("local_interface_alignment") or {}
    medium_redeclare = families.get("medium_redeclare_alignment") or {}

    first_failure_stage2_count = tier_stage_count(generation.get("tier_summary") or {}, "stage_2_")
    first_failure_total = int(generation.get("final_task_count") or 0)
    second_residual_stage2_count = second_residual_stage_count(one_step.get("second_residual_stage_distribution") or {}, "stage_2_")
    second_residual_total = int(one_step.get("task_count") or 0)

    stop_condition_1_met = (
        norm(local_interface.get("version_decision")) == "stage2_neighbor_component_local_interface_discovery_coverage_ready"
        and norm(local_interface.get("authority_confidence")) == "supported"
    )
    stop_condition_2_met = bool(medium_redeclare.get("family_ready"))
    stop_condition_3_met = (
        int(ledger.get("family_anchor_count") or 0) >= 3
        and first_failure_stage2_count >= 20
        and second_residual_stage2_count >= 20
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "family_ledger_path": str(Path(family_ledger_path).resolve()),
        "generation_census_path": str(Path(generation_census_path).resolve()),
        "one_step_repair_path": str(Path(one_step_repair_path).resolve()),
        "real_stage2_reference": {
            "first_failure_total": first_failure_total,
            "first_failure_stage2_count": first_failure_stage2_count,
            "second_residual_total": second_residual_total,
            "second_residual_stage2_count": second_residual_stage2_count,
        },
        "stop_condition_1_met": stop_condition_1_met,
        "stop_condition_2_met": stop_condition_2_met,
        "stop_condition_3_met": stop_condition_3_met,
        "stop_condition_3_basis": "stage2_target_alignment_supported_not_real_distribution_authority",
        "overall_stop_condition_met": stop_condition_1_met and stop_condition_2_met and stop_condition_3_met,
        "summary": (
            "All v0.3.x phase stop conditions are met when evaluated as curriculum-construction conditions rather than as a fresh real-distribution authority rerun."
            if stop_condition_1_met and stop_condition_2_met and stop_condition_3_met
            else "At least one v0.3.x phase stop condition remains unmet."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.34 Stop-Condition Audit",
                "",
                f"- stop_condition_1_met: `{payload.get('stop_condition_1_met')}`",
                f"- stop_condition_2_met: `{payload.get('stop_condition_2_met')}`",
                f"- stop_condition_3_met: `{payload.get('stop_condition_3_met')}`",
                f"- overall_stop_condition_met: `{payload.get('overall_stop_condition_met')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.34 stop-condition audit.")
    parser.add_argument("--family-ledger", default=str(DEFAULT_FAMILY_LEDGER_OUT_DIR / "summary.json"))
    parser.add_argument("--generation-census", default=str(DEFAULT_V0317_GENERATION_CENSUS_PATH))
    parser.add_argument("--one-step-repair", default=str(DEFAULT_V0317_ONE_STEP_REPAIR_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0334_stop_condition_audit(
        family_ledger_path=str(args.family_ledger),
        generation_census_path=str(args.generation_census),
        one_step_repair_path=str(args.one_step_repair),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "overall_stop_condition_met": payload.get("overall_stop_condition_met")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
