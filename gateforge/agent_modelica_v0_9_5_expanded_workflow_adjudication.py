from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_4_common import classify_baseline_against_pack
from .agent_modelica_v0_9_5_common import (
    DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR,
    DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR,
    DEFAULT_V093_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    dominant_barrier_family,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v095_expanded_workflow_adjudication(
    *,
    adjudication_input_table_path: str = str(DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR),
) -> dict:
    inputs = load_json(adjudication_input_table_path)
    v093 = load_json(v093_closeout_path)
    metrics = dict(inputs.get("frozen_baseline_metrics") or {})
    supported_pack = inputs.get("supported_thresholds") or {}
    partial_pack = inputs.get("partial_thresholds") or {}
    execution_posture = inputs.get("execution_posture_compatibility") or {}
    barrier_distribution = inputs.get("barrier_distribution") or {}
    characterization = (
        v093.get("expanded_workflow_profile_characterization")
        if isinstance(v093.get("expanded_workflow_profile_characterization"), dict)
        else {}
    )

    classification = classify_baseline_against_pack(
        metrics,
        supported_pack=supported_pack,
        partial_pack=partial_pack,
    )
    posture_ok = bool(execution_posture.get("compatible"))
    if not posture_ok:
        classification = "fallback_to_profile_clarification_or_expansion_needed"

    supported = classification == "expanded_workflow_readiness_supported"
    partial = classification == "expanded_workflow_readiness_partial_but_interpretable"
    fallback = classification == "fallback_to_profile_clarification_or_expansion_needed"
    route_count = int(sum([supported, partial, fallback]))
    dominant_barrier = dominant_barrier_family(
        {str(k): int(v) for k, v in (barrier_distribution or {}).items() if str(k).strip()}
    )

    if supported:
        why = "Supported is reached because the current expanded profile clears the frozen supported thresholds while preserving execution-posture compatibility and full barrier explainability."
    elif partial:
        why = "Partial but interpretable is reached because the current expanded profile clears the frozen partial floor, remains fully explainable, but stays below the frozen supported workflow-resolution and goal-alignment counts."
    elif fallback:
        why = "Fallback is triggered because the current expanded profile no longer clears even the frozen partial band or no longer preserves the required execution-posture semantics."
    else:
        why = "The adjudication result is invalid because the frozen pack did not yield a unique route."

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expanded_workflow_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if route_count == 1 else "FAIL",
        "final_adjudication_label": classification if route_count == 1 else "invalid_non_unique_route",
        "baseline_classification_under_frozen_pack": classification,
        "supported_check_pass": supported,
        "partial_check_pass": partial,
        "fallback_triggered": fallback,
        "execution_posture_semantics_preserved": posture_ok,
        "adjudication_route_count": route_count,
        "dominant_workflow_barrier_family": dominant_barrier,
        "why_this_label_is_correct": why,
        "workflow_resolution_case_count": metrics.get("workflow_resolution_case_count"),
        "goal_alignment_case_count": metrics.get("goal_alignment_case_count"),
        "profile_barrier_unclassified_count": characterization.get("profile_barrier_unclassified_count"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.5 Expanded Workflow Adjudication",
                "",
                f"- final_adjudication_label: `{payload['final_adjudication_label']}`",
                f"- adjudication_route_count: `{route_count}`",
                f"- dominant_workflow_barrier_family: `{dominant_barrier}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.5 expanded workflow adjudication artifact.")
    parser.add_argument("--adjudication-input-table", default=str(DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v095_expanded_workflow_adjudication(
        adjudication_input_table_path=str(args.adjudication_input_table),
        v093_closeout_path=str(args.v093_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "final_adjudication_label": payload.get("final_adjudication_label")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
