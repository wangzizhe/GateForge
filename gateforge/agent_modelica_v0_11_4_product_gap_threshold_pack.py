from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_4_common import (
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_THRESHOLD_PACK_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


# Frozen threshold constants for the carried 12-case product-gap substrate.
SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT: int = 4
SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT: int = 6

PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT: int = 3
PARTIAL_GOAL_ALIGNMENT_CASE_COUNT: int = 5


def _classify_baseline(
    workflow_resolution_case_count: int,
    goal_alignment_case_count: int,
) -> str:
    if (
        workflow_resolution_case_count >= SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT
        and goal_alignment_case_count >= SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT
    ):
        return "product_gap_supported"
    if (
        workflow_resolution_case_count >= PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT
        and goal_alignment_case_count >= PARTIAL_GOAL_ALIGNMENT_CASE_COUNT
    ):
        return "product_gap_partial_but_interpretable"
    return "product_gap_fallback"


def _check_anti_tautology(
    workflow_resolution_case_count: int,
    goal_alignment_case_count: int,
) -> bool:
    classification = _classify_baseline(workflow_resolution_case_count, goal_alignment_case_count)
    if classification == "product_gap_supported":
        return False
    return (
        SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT > workflow_resolution_case_count
        or SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT > goal_alignment_case_count
    )


def _check_integer_safe() -> bool:
    return (
        SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT > PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT
        and SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT > PARTIAL_GOAL_ALIGNMENT_CASE_COUNT
    )


def _check_execution_posture_semantics(input_table: dict) -> bool:
    note = str(input_table.get("execution_posture_semantics_note") or "")
    total = int(input_table.get("product_gap_case_count") or 0)
    wr = int(input_table.get("workflow_resolution_case_count") or 0)
    ga = int(input_table.get("goal_alignment_case_count") or 0)
    sf = int(input_table.get("surface_fix_only_case_count") or 0)
    un = int(input_table.get("unresolved_case_count") or 0)
    return (
        total > 0
        and ga == wr + sf
        and total >= wr + sf + un
        and "product-gap interpretation" in note
        and "product readiness" in note
    )


def build_v114_product_gap_threshold_pack(
    *,
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_THRESHOLD_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    input_table = load_json(threshold_input_table_path)

    wr = int(input_table.get("workflow_resolution_case_count") or 0)
    ga = int(input_table.get("goal_alignment_case_count") or 0)

    baseline_classification = _classify_baseline(wr, ga)
    anti_tautology_pass = _check_anti_tautology(wr, ga)
    integer_safe_pass = _check_integer_safe()
    execution_posture_semantics_preserved = _check_execution_posture_semantics(input_table)

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_product_gap_threshold_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS" if (anti_tautology_pass and integer_safe_pass) else ("PARTIAL" if integer_safe_pass is False and anti_tautology_pass else "FAIL"),
        "supported_thresholds": {
            "workflow_resolution_case_count": SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT,
            "goal_alignment_case_count": SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT,
            "semantics": "both conditions must be met simultaneously",
        },
        "partial_but_interpretable_thresholds": {
            "workflow_resolution_case_count": PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT,
            "goal_alignment_case_count": PARTIAL_GOAL_ALIGNMENT_CASE_COUNT,
            "semantics": "both conditions must be met simultaneously",
        },
        "fallback_thresholds": {
            "trigger_conditions": [
                "baseline fails the frozen partial band",
                "the product-gap profile is too weak or semantically misaligned for the intended interpretation",
            ]
        },
        "anti_tautology_pass": anti_tautology_pass,
        "integer_safe_pass": integer_safe_pass,
        "execution_posture_semantics_preserved": execution_posture_semantics_preserved,
        "baseline_classification_under_frozen_pack": baseline_classification,
        "baseline_workflow_resolution_case_count": wr,
        "baseline_goal_alignment_case_count": ga,
        "execution_posture_note": str(input_table.get("execution_posture_semantics_note") or ""),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.4 Product-Gap Threshold Pack",
                "",
                f"- baseline_classification_under_frozen_pack: `{baseline_classification}`",
                f"- anti_tautology_pass: `{anti_tautology_pass}`",
                f"- integer_safe_pass: `{integer_safe_pass}`",
                f"- execution_posture_semantics_preserved: `{execution_posture_semantics_preserved}`",
                f"- supported: wr>={SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT}, ga>={SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT}",
                f"- partial:  wr>={PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT}, ga>={PARTIAL_GOAL_ALIGNMENT_CASE_COUNT}",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.4 product-gap threshold pack.")
    parser.add_argument("--threshold-input-table", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v114_product_gap_threshold_pack(
        threshold_input_table_path=str(args.threshold_input_table),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "baseline_classification_under_frozen_pack": payload.get("baseline_classification_under_frozen_pack"),
                "anti_tautology_pass": payload.get("anti_tautology_pass"),
                "integer_safe_pass": payload.get("integer_safe_pass"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
