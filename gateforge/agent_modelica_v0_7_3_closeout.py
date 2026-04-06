from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_7_3_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DECISION_ADJUDICATION_OUT_DIR,
    DEFAULT_DECISION_INPUT_TABLE_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_7_3_decision_adjudication import build_v073_decision_adjudication
from .agent_modelica_v0_7_3_decision_input_table import build_v073_decision_input_table
from .agent_modelica_v0_7_3_handoff_integrity import build_v073_handoff_integrity


def build_v073_closeout(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    decision_input_table_path: str = str(DEFAULT_DECISION_INPUT_TABLE_OUT_DIR / "summary.json"),
    decision_adjudication_path: str = str(DEFAULT_DECISION_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v073_handoff_integrity(out_dir=str(Path(handoff_integrity_path).parent))
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        payload = {
            "schema_version": f"{SCHEMA_PREFIX}_closeout",
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "closeout_status": "V0_7_3_HANDOFF_SUBSTRATE_INVALID",
            "conclusion": {
                "version_decision": "v0_7_3_handoff_substrate_invalid",
                "decision_input_status": "invalid",
                "stable_coverage_share_pct_stable": None,
                "spillover_share_pct_stable": None,
                "legacy_bucket_mapping_rate_pct_stable": None,
                "complexity_pressure_profile": None,
                "open_world_candidate_gap_summary": None,
                "v0_7_4_open_world_readiness_supported_floor": None,
                "v0_7_4_open_world_readiness_partial_floor": None,
                "v0_7_4_fallback_to_targeted_expansion_floor": None,
                "v0_7_4_handoff_mode": "repair_mid_phase_decision_substrate_first",
            },
            "handoff_integrity": integrity,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", payload)
        write_text(out_root / "summary.md", "# v0.7.3 Closeout\n")
        return payload

    if not Path(decision_input_table_path).exists():
        build_v073_decision_input_table(out_dir=str(Path(decision_input_table_path).parent))
    if not Path(decision_adjudication_path).exists():
        build_v073_decision_adjudication(
            decision_input_table_path=decision_input_table_path,
            out_dir=str(Path(decision_adjudication_path).parent),
        )

    table = load_json(decision_input_table_path)
    adjudication = load_json(decision_adjudication_path)
    status = str(adjudication.get("decision_input_status") or "invalid")

    if status == "ready":
        version_decision = "v0_7_3_phase_decision_inputs_ready"
        handoff_mode = "run_mid_phase_readiness_adjudication"
    elif status == "partial":
        version_decision = "v0_7_3_phase_decision_inputs_partial"
        handoff_mode = "continue_mid_phase_decision_preparation"
    else:
        version_decision = "v0_7_3_handoff_substrate_invalid"
        handoff_mode = "repair_mid_phase_decision_substrate_first"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "closeout_status": {
            "ready": "V0_7_3_PHASE_DECISION_INPUTS_READY",
            "partial": "V0_7_3_PHASE_DECISION_INPUTS_PARTIAL",
            "invalid": "V0_7_3_HANDOFF_SUBSTRATE_INVALID",
        }[status],
        "conclusion": {
            "version_decision": version_decision,
            "decision_input_status": status,
            "stable_coverage_share_pct_stable": adjudication.get("stable_coverage_share_pct_stable"),
            "spillover_share_pct_stable": adjudication.get("spillover_share_pct_stable"),
            "legacy_bucket_mapping_rate_pct_stable": adjudication.get("legacy_bucket_mapping_rate_pct_stable"),
            "complexity_pressure_profile": adjudication.get("complexity_pressure_profile"),
            "open_world_candidate_gap_summary": adjudication.get("open_world_candidate_gap_summary"),
            "v0_7_4_open_world_readiness_supported_floor": table.get("v0_7_4_open_world_readiness_supported_floor"),
            "v0_7_4_open_world_readiness_partial_floor": table.get("v0_7_4_open_world_readiness_partial_floor"),
            "v0_7_4_fallback_to_targeted_expansion_floor": table.get("v0_7_4_fallback_to_targeted_expansion_floor"),
            "v0_7_4_handoff_mode": handoff_mode,
        },
        "handoff_integrity": integrity,
        "decision_input_table": table,
        "decision_adjudication": adjudication,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.3 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- decision_input_status: `{status}`",
                f"- stable_coverage_share_pct_stable: `{adjudication.get('stable_coverage_share_pct_stable')}`",
                f"- spillover_share_pct_stable: `{adjudication.get('spillover_share_pct_stable')}`",
                f"- open_world_candidate_gap_summary: `{adjudication.get('open_world_candidate_gap_summary')}`",
                f"- v0_7_4_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.3 closeout.")
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--decision-input-table", default=str(DEFAULT_DECISION_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--decision-adjudication", default=str(DEFAULT_DECISION_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v073_closeout(
        handoff_integrity_path=str(args.handoff_integrity),
        decision_input_table_path=str(args.decision_input_table),
        decision_adjudication_path=str(args.decision_adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
