from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_5_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V054_CLOSEOUT_PATH,
    DEFAULT_WIDENED_EXECUTION_OUT_DIR,
    DEFAULT_WIDENED_MANIFEST_OUT_DIR,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_5_handoff_integrity import build_v055_handoff_integrity
from .agent_modelica_v0_5_5_widened_adjudication import build_v055_widened_adjudication
from .agent_modelica_v0_5_5_widened_execution import build_v055_widened_execution
from .agent_modelica_v0_5_5_widened_manifest import build_v055_widened_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v055_closeout(
    *,
    v0_5_4_closeout_path: str = str(DEFAULT_V054_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    widened_manifest_path: str = str(DEFAULT_WIDENED_MANIFEST_OUT_DIR / "summary.json"),
    widened_execution_path: str = str(DEFAULT_WIDENED_EXECUTION_OUT_DIR / "summary.json"),
    adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v055_handoff_integrity(v0_5_4_closeout_path=v0_5_4_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))
    if not Path(widened_manifest_path).exists():
        build_v055_widened_manifest(
            v0_5_4_closeout_path=v0_5_4_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            out_dir=str(Path(widened_manifest_path).parent),
        )
    if not Path(widened_execution_path).exists():
        build_v055_widened_execution(
            v0_5_4_closeout_path=v0_5_4_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            widened_manifest_path=str(widened_manifest_path),
            out_dir=str(Path(widened_execution_path).parent),
        )
    if not Path(adjudication_path).exists():
        build_v055_widened_adjudication(
            v0_5_4_closeout_path=v0_5_4_closeout_path,
            handoff_integrity_path=str(handoff_integrity_path),
            widened_manifest_path=str(widened_manifest_path),
            widened_execution_path=str(widened_execution_path),
            out_dir=str(Path(adjudication_path).parent),
        )

    integrity = load_json(handoff_integrity_path)
    manifest = load_json(widened_manifest_path)
    execution = load_json(widened_execution_path)
    adjudication = load_json(adjudication_path)

    if not bool(integrity.get("handoff_integrity_ok")):
        version_decision = "v0_5_5_handoff_substrate_invalid"
        widened_status = "not_ready"
        branch_status = "not_ready_under_widening"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"
    elif bool(adjudication.get("widened_ready")):
        version_decision = "v0_5_5_targeted_expansion_widened_ready"
        widened_status = "widened_ready"
        branch_status = "widened_and_stable"
        handoff_mode = "decide_if_targeted_expansion_deserves_family_level_promotion"
    elif float(execution.get("scope_creep_rate_pct") or 0.0) > 0.0:
        version_decision = "v0_5_5_targeted_expansion_not_ready"
        widened_status = "not_ready"
        branch_status = "not_ready_under_widening"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"
    elif bool(manifest.get("widened_manifest_frozen")) and float(execution.get("target_first_failure_hit_rate_pct") or 0.0) >= 80.0 and float(execution.get("patch_applied_rate_pct") or 0.0) >= 70.0 and (
        float(execution.get("second_residual_exposure_rate_pct") or 0.0) < 50.0 or float(execution.get("second_residual_bounded_rate_pct") or 0.0) < 50.0
    ):
        version_decision = "v0_5_5_targeted_expansion_partial"
        widened_status = "partial"
        branch_status = "widened_but_fragile"
        handoff_mode = "repair_targeted_expansion_widening_gaps_first"
    elif bool(manifest.get("widened_manifest_frozen")):
        version_decision = "v0_5_5_targeted_expansion_partial"
        widened_status = "partial"
        branch_status = "still_small_but_real"
        handoff_mode = "repair_targeted_expansion_widening_gaps_first"
    else:
        version_decision = "v0_5_5_targeted_expansion_not_ready"
        widened_status = "not_ready"
        branch_status = "not_ready_under_widening"
        handoff_mode = "return_to_boundary_mapping_for_reassessment"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_5_5_TARGETED_EXPANSION_WIDENED_READY",
        "conclusion": {
            "version_decision": version_decision,
            "targeted_expansion_widened_status": widened_status,
            "branch_status": branch_status,
            "widened_ready": adjudication.get("widened_ready"),
            "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
            "v0_5_6_handoff_mode": handoff_mode,
            "v0_5_6_primary_eval_question": "Given the widened confirmation result, should this targeted expansion now be promoted toward higher-level authority, or does it still remain a bounded but limited branch?",
        },
        "handoff_integrity": integrity,
        "widened_manifest": manifest,
        "widened_execution": execution,
        "widened_adjudication": adjudication,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.5 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- branch_status: `{branch_status}`",
                f"- v0_5_6_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.5 widened confirmation closeout.")
    parser.add_argument("--v0-5-4-closeout", default=str(DEFAULT_V054_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--widened-manifest", default=str(DEFAULT_WIDENED_MANIFEST_OUT_DIR / "summary.json"))
    parser.add_argument("--widened-execution", default=str(DEFAULT_WIDENED_EXECUTION_OUT_DIR / "summary.json"))
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v055_closeout(
        v0_5_4_closeout_path=str(args.v0_5_4_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        widened_manifest_path=str(args.widened_manifest),
        widened_execution_path=str(args.widened_execution),
        adjudication_path=str(args.adjudication),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
