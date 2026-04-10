from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_5_first_real_origin_threshold_pack import (
    PARTIAL_GOAL_ALIGNMENT_CASE_COUNT,
    PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT,
    SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT,
    SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT,
)
from .agent_modelica_v0_10_6_common import (
    DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V105_CLOSEOUT_PATH,
    DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH,
    EXPECTED_EXECUTION_SOURCE,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v106_real_origin_adjudication_input_table(
    *,
    v105_closeout_path: str = str(DEFAULT_V105_CLOSEOUT_PATH),
    v105_threshold_input_table_path: str = str(DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    v105_closeout = load_json(v105_closeout_path)
    v105_threshold_input = load_json(v105_threshold_input_table_path)
    v104_closeout = load_json(v104_closeout_path)

    conclusion = v105_closeout.get("conclusion") if isinstance(v105_closeout.get("conclusion"), dict) else {}
    threshold_input = (
        v105_closeout.get("real_origin_threshold_input_table")
        if isinstance(v105_closeout.get("real_origin_threshold_input_table"), dict)
        else v105_threshold_input
    )
    replay_sidecar = threshold_input.get("replay_floor_sidecar") if isinstance(threshold_input.get("replay_floor_sidecar"), dict) else {}
    v104_conclusion = v104_closeout.get("conclusion") if isinstance(v104_closeout.get("conclusion"), dict) else {}
    characterization = (
        v104_closeout.get("real_origin_workflow_profile_characterization")
        if isinstance(v104_closeout.get("real_origin_workflow_profile_characterization"), dict)
        else {}
    )

    actual_execution_source = str(replay_sidecar.get("execution_source") or "")
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_real_origin_adjudication_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "frozen_baseline_metrics": {
            "real_origin_substrate_case_count": threshold_input.get("real_origin_substrate_case_count"),
            "workflow_resolution_case_count": conclusion.get("workflow_resolution_case_count"),
            "goal_alignment_case_count": conclusion.get("goal_alignment_case_count"),
            "surface_fix_only_case_count": conclusion.get("surface_fix_only_case_count"),
            "unresolved_case_count": conclusion.get("unresolved_case_count"),
            "profile_non_success_unclassified_count": v104_conclusion.get("profile_non_success_unclassified_count"),
            "execution_source": actual_execution_source,
        },
        "supported_thresholds": {
            "workflow_resolution_case_count": SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT,
            "goal_alignment_case_count": SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT,
        },
        "partial_thresholds": {
            "workflow_resolution_case_count": PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT,
            "goal_alignment_case_count": PARTIAL_GOAL_ALIGNMENT_CASE_COUNT,
        },
        "fallback_rule_summary": {
            "trigger_conditions": (
                (v105_closeout.get("first_real_origin_threshold_pack") or {}).get("fallback_definition", {})
            ).get("trigger_conditions", []),
        },
        "non_success_label_distribution": characterization.get("non_success_label_distribution"),
        "execution_posture_compatibility": {
            "actual_execution_source": actual_execution_source,
            "required_execution_source": EXPECTED_EXECUTION_SOURCE,
            "compatible": actual_execution_source == EXPECTED_EXECUTION_SOURCE,
        },
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.6 Real-Origin Adjudication Input Table",
                "",
                f"- workflow_resolution_case_count: `{payload['frozen_baseline_metrics']['workflow_resolution_case_count']}`",
                f"- goal_alignment_case_count: `{payload['frozen_baseline_metrics']['goal_alignment_case_count']}`",
                f"- execution_posture_compatible: `{payload['execution_posture_compatibility']['compatible']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.6 real-origin adjudication input table.")
    parser.add_argument("--v105-closeout", default=str(DEFAULT_V105_CLOSEOUT_PATH))
    parser.add_argument("--v105-threshold-input-table", default=str(DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v106_real_origin_adjudication_input_table(
        v105_closeout_path=str(args.v105_closeout),
        v105_threshold_input_table_path=str(args.v105_threshold_input_table),
        v104_closeout_path=str(args.v104_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "execution_posture_compatible": (payload.get("execution_posture_compatibility") or {}).get("compatible")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
