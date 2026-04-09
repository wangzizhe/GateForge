from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_9_5_common import (
    DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH,
    DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v095_adjudication_input_table(
    *,
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v094_threshold_input_table_path: str = str(DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH),
    v094_expanded_threshold_pack_path: str = str(DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH),
    out_dir: str = str(DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR),
) -> dict:
    v093 = load_json(v093_closeout_path)
    threshold_input = load_json(v094_threshold_input_table_path)
    threshold_pack = load_json(v094_expanded_threshold_pack_path)

    characterization = (
        v093.get("expanded_workflow_profile_characterization")
        if isinstance(v093.get("expanded_workflow_profile_characterization"), dict)
        else {}
    )
    replay = v093.get("expanded_profile_replay_pack") if isinstance(v093.get("expanded_profile_replay_pack"), dict) else {}
    metrics = dict(threshold_input.get("frozen_baseline_metrics") or {})

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_adjudication_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "frozen_baseline_metrics": metrics,
        "supported_thresholds": threshold_pack.get("supported_threshold_pack"),
        "partial_thresholds": threshold_pack.get("partial_threshold_pack"),
        "fallback_rule_summary": threshold_pack.get("fallback_rule_summary"),
        "barrier_distribution": characterization.get("barrier_label_distribution"),
        "execution_posture_compatibility": {
            "actual_execution_source": replay.get("execution_source"),
            "required_execution_source": (
                (threshold_pack.get("supported_threshold_pack") or {})
                .get("execution_posture", {})
                .get("allowed_execution_source")
            ),
            "compatible": str(metrics.get("execution_source") or "")
            == str(
                ((threshold_pack.get("supported_threshold_pack") or {}).get("execution_posture", {})).get(
                    "allowed_execution_source"
                )
                or ""
            ),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.5 Adjudication Input Table",
                "",
                f"- workflow_resolution_case_count: `{metrics.get('workflow_resolution_case_count')}`",
                f"- goal_alignment_case_count: `{metrics.get('goal_alignment_case_count')}`",
                f"- execution_posture_compatible: `{payload['execution_posture_compatibility']['compatible']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.5 adjudication input table.")
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v094-threshold-input-table", default=str(DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH))
    parser.add_argument("--v094-expanded-threshold-pack", default=str(DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v095_adjudication_input_table(
        v093_closeout_path=str(args.v093_closeout),
        v094_threshold_input_table_path=str(args.v094_threshold_input_table),
        v094_expanded_threshold_pack_path=str(args.v094_expanded_threshold_pack),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
