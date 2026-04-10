from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_5_common import (
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_THRESHOLD_PACK_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)

# ---------------------------------------------------------------------------
# Frozen threshold constants.
#
# These are declared constants, NOT derived at runtime from the current baseline.
# The engineering judgment behind these values:
#   - The v0.10.4 characterized baseline has workflow_resolution=4, goal_alignment=6
#     on a 12-case real-origin substrate.
#   - SUPPORTED band must be strictly stronger than the baseline on ≥1 main metric,
#     so that the baseline cannot tautologically self-classify as supported.
#   - PARTIAL band must include the current baseline, confirming the freeze
#     correctly positions it as partial_but_interpretable rather than fallback.
# ---------------------------------------------------------------------------

# Supported band: strictly stronger than baseline (4 wr, 6 ga) on both metrics
SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT: int = 6
SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT: int = 8

# Partial band: includes the current baseline (4 >= 3, 6 >= 5)
PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT: int = 3
PARTIAL_GOAL_ALIGNMENT_CASE_COUNT: int = 5


def _classify_baseline(
    workflow_resolution_case_count: int,
    goal_alignment_case_count: int,
) -> str:
    """Classify a case count pair against the frozen threshold bands.

    Comparisons operate on integer case counts (not floating-point percentages).
    """
    if (
        workflow_resolution_case_count >= SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT
        and goal_alignment_case_count >= SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT
    ):
        return "real_origin_workflow_readiness_supported"
    if (
        workflow_resolution_case_count >= PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT
        and goal_alignment_case_count >= PARTIAL_GOAL_ALIGNMENT_CASE_COUNT
    ):
        return "real_origin_workflow_readiness_partial_but_interpretable"
    return "real_origin_workflow_readiness_fallback"


def _check_anti_tautology(
    workflow_resolution_case_count: int,
    goal_alignment_case_count: int,
) -> bool:
    """Return True iff the anti-tautology rule is satisfied.

    Anti-tautology requirements:
    - The current baseline must NOT classify as supported.
    - The supported band must be strictly stronger than the baseline on ≥1 main metric.
    """
    classification = _classify_baseline(workflow_resolution_case_count, goal_alignment_case_count)
    if classification == "real_origin_workflow_readiness_supported":
        return False
    supported_strictly_stronger = (
        SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT > workflow_resolution_case_count
        or SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT > goal_alignment_case_count
    )
    return supported_strictly_stronger


def _check_integer_safe() -> bool:
    """Return True iff the frozen threshold bands satisfy the integer-safe rule.

    Requirements:
    - Thresholds are stored as integer case counts (enforced by the type annotations above).
    - Supported and partial bands must not overlap or invert on either metric.
    """
    return (
        SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT > PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT
        and SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT > PARTIAL_GOAL_ALIGNMENT_CASE_COUNT
    )


def _check_execution_posture_semantics(input_table: dict) -> bool:
    """Return True iff the workflow-level interpretation frame is structurally preserved.

    Checks that the four workflow metrics are mutually consistent:
      goal_alignment == workflow_resolution + surface_fix_only
      real_origin_substrate_case_count >= workflow_resolution + surface_fix_only + unresolved
    """
    total = int(input_table.get("real_origin_substrate_case_count") or 0)
    wr = int(input_table.get("workflow_resolution_case_count") or 0)
    ga = int(input_table.get("goal_alignment_case_count") or 0)
    sf = int(input_table.get("surface_fix_only_case_count") or 0)
    un = int(input_table.get("unresolved_case_count") or 0)
    if total <= 0:
        return False
    goal_alignment_consistent = ga == wr + sf
    total_consistent = total >= wr + sf + un
    return goal_alignment_consistent and total_consistent


def build_v105_first_real_origin_threshold_pack(
    *,
    threshold_input_table_path: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_THRESHOLD_PACK_OUT_DIR),
) -> dict:
    """Freeze the first real-origin workflow readiness threshold pack.

    Hard rule: threshold values are declared constants above and must not be
    dynamically recomputed from the current baseline at runtime.
    """
    out_root = Path(out_dir)
    input_table = load_json(threshold_input_table_path)

    wrc = int(input_table.get("workflow_resolution_case_count") or 0)
    gac = int(input_table.get("goal_alignment_case_count") or 0)

    baseline_classification = _classify_baseline(wrc, gac)
    anti_tautology_pass = _check_anti_tautology(wrc, gac)
    integer_safe_pass = _check_integer_safe()
    execution_posture_semantics_preserved = _check_execution_posture_semantics(input_table)

    supported_thresholds = {
        "workflow_resolution_case_count": SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT,
        "goal_alignment_case_count": SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT,
        "semantics": "both conditions must be met simultaneously",
    }
    partial_thresholds = {
        "workflow_resolution_case_count": PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT,
        "goal_alignment_case_count": PARTIAL_GOAL_ALIGNMENT_CASE_COUNT,
        "semantics": "both conditions must be met simultaneously",
    }
    fallback_definition = {
        "trigger_conditions": [
            "baseline fails the frozen partial band",
            "replay-floor semantics from v0.10.4 are no longer preserved",
            "non-success explainability semantics collapse",
            "execution-posture semantics no longer match the frozen real-origin profile basis",
        ],
        "note": "Some conditions are pre-validated by handoff integrity; the threshold pack carries them explicitly.",
    }

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_first_real_origin_threshold_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS" if (anti_tautology_pass and integer_safe_pass) else "FAIL",
        "supported_thresholds": supported_thresholds,
        "partial_thresholds": partial_thresholds,
        "fallback_definition": fallback_definition,
        "anti_tautology_pass": anti_tautology_pass,
        "integer_safe_pass": integer_safe_pass,
        "execution_posture_semantics_preserved": execution_posture_semantics_preserved,
        "baseline_classification_under_frozen_pack": baseline_classification,
        "baseline_workflow_resolution_case_count": wrc,
        "baseline_goal_alignment_case_count": gac,
        "execution_posture_note": (
            "Thresholds are frozen constants derived from engineering judgment on the "
            "v0.10.4 real-origin characterized profile; they are not produced by a formula "
            "that mirrors the current baseline."
        ),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.5 First Real-Origin Threshold Pack",
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
    parser = argparse.ArgumentParser(description="Build the v0.10.5 first real-origin threshold pack.")
    parser.add_argument(
        "--threshold-input-table",
        default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v105_first_real_origin_threshold_pack(
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
