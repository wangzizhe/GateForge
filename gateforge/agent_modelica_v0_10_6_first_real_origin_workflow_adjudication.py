from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_5_first_real_origin_threshold_pack import _classify_baseline
from .agent_modelica_v0_10_6_common import (
    DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR,
    DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    SCHEMA_PREFIX,
    dominant_non_success_family,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v106_first_real_origin_workflow_adjudication(
    *,
    real_origin_adjudication_input_table_path: str = str(
        DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"
    ),
    out_dir: str = str(DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    inputs = load_json(real_origin_adjudication_input_table_path)
    metrics = dict(inputs.get("frozen_baseline_metrics") or {})
    distribution = {str(k): int(v) for k, v in (inputs.get("non_success_label_distribution") or {}).items() if str(k).strip()}
    execution_posture = inputs.get("execution_posture_compatibility") or {}

    workflow_resolution_case_count = int(metrics.get("workflow_resolution_case_count") or 0)
    goal_alignment_case_count = int(metrics.get("goal_alignment_case_count") or 0)
    profile_non_success_unclassified_count = int(metrics.get("profile_non_success_unclassified_count") or 0)

    classification = _classify_baseline(workflow_resolution_case_count, goal_alignment_case_count)
    execution_posture_ok = bool(execution_posture.get("compatible"))
    explainability_ok = profile_non_success_unclassified_count == 0

    if not execution_posture_ok or not explainability_ok:
        classification = "real_origin_workflow_readiness_fallback"

    supported = classification == "real_origin_workflow_readiness_supported"
    partial = classification == "real_origin_workflow_readiness_partial_but_interpretable"
    fallback = classification == "real_origin_workflow_readiness_fallback"
    route_count = int(sum([supported, partial, fallback]))
    dominant_non_success = dominant_non_success_family(distribution)

    if supported:
        why = (
            "Supported is reached because the current real-origin profile clears the frozen supported "
            "thresholds while preserving execution-posture semantics and full non-success explainability."
        )
    elif partial:
        why = (
            "Partial but interpretable is reached because the current real-origin profile clears the frozen "
            "partial floor, remains explainable, but stays below the frozen supported workflow-resolution "
            "and goal-alignment counts."
        )
    elif fallback:
        why = (
            "Fallback is triggered because the current real-origin profile no longer clears even the frozen "
            "partial band or no longer preserves the required execution-posture or explainability semantics."
        )
    else:
        why = "The adjudication result is invalid because the frozen real-origin pack did not yield a unique route."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_first_real_origin_workflow_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if route_count == 1 else "FAIL",
        "final_adjudication_label": classification if route_count == 1 else "invalid_non_unique_route",
        "baseline_classification_under_frozen_pack": classification,
        "supported_check_pass": supported,
        "partial_check_pass": partial,
        "fallback_triggered": fallback,
        "execution_posture_semantics_preserved": execution_posture_ok,
        "non_success_explainability_preserved": explainability_ok,
        "adjudication_route_count": route_count,
        "dominant_non_success_label_family": dominant_non_success,
        "why_this_label_is_correct": why,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.6 First Real-Origin Workflow Adjudication",
                "",
                f"- final_adjudication_label: `{payload['final_adjudication_label']}`",
                f"- adjudication_route_count: `{route_count}`",
                f"- dominant_non_success_label_family: `{dominant_non_success}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.6 first real-origin workflow adjudication artifact.")
    parser.add_argument(
        "--real-origin-adjudication-input-table",
        default=str(DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v106_first_real_origin_workflow_adjudication(
        real_origin_adjudication_input_table_path=str(args.real_origin_adjudication_input_table),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "final_adjudication_label": payload.get("final_adjudication_label")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
