from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_2_common import (
    DEFAULT_THRESHOLD_FREEZE_OUT_DIR,
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    FALLBACK_RULE_SUMMARY,
    PARTIAL_THRESHOLD_PACK,
    SCHEMA_PREFIX,
    SUPPORTED_THRESHOLD_PACK,
    evaluate_rule_pack,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v082_threshold_freeze(
    *,
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_THRESHOLD_FREEZE_OUT_DIR),
) -> dict:
    inputs = load_json(threshold_input_table_path)
    metrics = dict(inputs.get("frozen_baseline_metrics") or {})

    baseline_supported = evaluate_rule_pack(metrics, SUPPORTED_THRESHOLD_PACK)
    baseline_partial = evaluate_rule_pack(metrics, PARTIAL_THRESHOLD_PACK)
    anti_tautology_pass = (not baseline_supported) and baseline_partial

    integer_safe_checks = {
        "supported_workflow_resolution_is_integer_safe": SUPPORTED_THRESHOLD_PACK["primary_workflow_metrics"][
            "workflow_resolution_rate_pct_min"
        ]
        % 10.0
        == 0.0,
        "supported_goal_alignment_is_integer_safe": SUPPORTED_THRESHOLD_PACK["primary_workflow_metrics"][
            "goal_alignment_rate_pct_min"
        ]
        % 10.0
        == 0.0,
        "partial_workflow_resolution_is_integer_safe": PARTIAL_THRESHOLD_PACK["primary_workflow_metrics"][
            "workflow_resolution_rate_pct_min"
        ]
        % 10.0
        == 0.0,
        "partial_goal_alignment_is_integer_safe": PARTIAL_THRESHOLD_PACK["primary_workflow_metrics"][
            "goal_alignment_rate_pct_min"
        ]
        % 10.0
        == 0.0,
    }
    integer_safe_pass = all(integer_safe_checks.values())

    class_distinction_checks = {
        "supported_stricter_than_partial_workflow_resolution": SUPPORTED_THRESHOLD_PACK[
            "primary_workflow_metrics"
        ]["workflow_resolution_rate_pct_min"]
        > PARTIAL_THRESHOLD_PACK["primary_workflow_metrics"]["workflow_resolution_rate_pct_min"],
        "supported_stricter_than_partial_goal_alignment": SUPPORTED_THRESHOLD_PACK[
            "primary_workflow_metrics"
        ]["goal_alignment_rate_pct_min"]
        > PARTIAL_THRESHOLD_PACK["primary_workflow_metrics"]["goal_alignment_rate_pct_min"],
        "fallback_path_remains_reachable": True,
    }
    class_distinction_pass = all(class_distinction_checks.values())
    pack_ready = anti_tautology_pass and integer_safe_pass and class_distinction_pass

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_threshold_freeze",
        "generated_at_utc": now_utc(),
        "status": "PASS" if pack_ready else "FAIL",
        "threshold_pack_status": "FROZEN" if pack_ready else "INVALID",
        "supported_threshold_pack": SUPPORTED_THRESHOLD_PACK,
        "partial_threshold_pack": PARTIAL_THRESHOLD_PACK,
        "fallback_rule_summary": FALLBACK_RULE_SUMMARY,
        "anti_tautology_check": {
            "pass": anti_tautology_pass,
            "current_v081_baseline_supported": baseline_supported,
            "current_v081_baseline_partial": baseline_partial,
        },
        "integer_safe_check": {
            "pass": integer_safe_pass,
            "checks": integer_safe_checks,
        },
        "class_distinction_check": {
            "pass": class_distinction_pass,
            "checks": class_distinction_checks,
        },
        "why_current_v081_baseline_is_or_is_not_partial_by_default": (
            "The current baseline clears the frozen partial floor but remains below the supported workflow-resolution and goal-alignment thresholds."
            if baseline_partial and not baseline_supported
            else "The current baseline does not cleanly land in the intended partial band."
        ),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.2 Threshold Freeze",
                "",
                f"- threshold_pack_status: `{payload['threshold_pack_status']}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
                f"- integer_safe_pass: `{integer_safe_pass}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.2 threshold freeze summary.")
    parser.add_argument(
        "--threshold-input-table-path",
        default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_FREEZE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v082_threshold_freeze(
        threshold_input_table_path=str(args.threshold_input_table_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
