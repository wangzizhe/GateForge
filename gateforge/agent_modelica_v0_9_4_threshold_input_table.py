from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_9_4_common import (
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_V093_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    integer_safe_display,
    load_json,
    now_utc,
    pct_to_case_count,
    share_pct,
    write_json,
    write_text,
)


def build_v094_threshold_input_table(
    *,
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR),
) -> dict:
    closeout = load_json(v093_closeout_path)
    replay = closeout.get("expanded_profile_replay_pack") if isinstance(closeout.get("expanded_profile_replay_pack"), dict) else {}
    characterization = (
        closeout.get("expanded_workflow_profile_characterization")
        if isinstance(closeout.get("expanded_workflow_profile_characterization"), dict)
        else {}
    )
    task_count = int(characterization.get("expanded_substrate_size") or len(characterization.get("case_characterization_table") or []))
    barrier_distribution = characterization.get("barrier_label_distribution") if isinstance(characterization.get("barrier_label_distribution"), dict) else {}

    workflow_resolution_rate_pct = float(characterization.get("workflow_resolution_rate_pct") or 0.0)
    goal_alignment_rate_pct = float(characterization.get("goal_alignment_rate_pct") or 0.0)
    surface_fix_only_rate_pct = float(characterization.get("surface_fix_only_rate_pct") or 0.0)
    unresolved_rate_pct = float(characterization.get("unresolved_rate_pct") or 0.0)

    workflow_resolution_case_count = pct_to_case_count(workflow_resolution_rate_pct, task_count)
    goal_alignment_case_count = pct_to_case_count(goal_alignment_rate_pct, task_count)
    surface_fix_only_case_count = pct_to_case_count(surface_fix_only_rate_pct, task_count)
    unresolved_case_count = pct_to_case_count(unresolved_rate_pct, task_count)
    goal_artifact_case_count = int(barrier_distribution.get("goal_artifact_missing_after_surface_fix") or 0)
    dispatch_case_count = int(barrier_distribution.get("dispatch_or_policy_limited_unresolved") or 0)
    spillover_case_count = int(barrier_distribution.get("workflow_spillover_unresolved") or 0)

    metrics = {
        "task_count": task_count,
        "execution_source": str(replay.get("execution_source") or ""),
        "workflow_resolution_case_count": workflow_resolution_case_count,
        "goal_alignment_case_count": goal_alignment_case_count,
        "surface_fix_only_case_count": surface_fix_only_case_count,
        "unresolved_case_count": unresolved_case_count,
        "goal_artifact_missing_after_surface_fix_case_count": goal_artifact_case_count,
        "dispatch_or_policy_limited_case_count": dispatch_case_count,
        "workflow_spillover_case_count": spillover_case_count,
        "workflow_resolution_rate_pct": workflow_resolution_rate_pct,
        "goal_alignment_rate_pct": goal_alignment_rate_pct,
        "surface_fix_only_rate_pct": surface_fix_only_rate_pct,
        "unresolved_rate_pct": unresolved_rate_pct,
        "goal_artifact_missing_after_surface_fix_share_pct": share_pct(goal_artifact_case_count, task_count),
        "dispatch_or_policy_limited_share_pct": share_pct(dispatch_case_count, task_count),
        "workflow_spillover_share_pct": share_pct(spillover_case_count, task_count),
        "profile_barrier_unclassified_count": int(characterization.get("profile_barrier_unclassified_count") or 0),
        "barrier_label_coverage_rate_pct": float(characterization.get("barrier_label_coverage_rate_pct") or 0.0),
        "surface_fix_only_explained_rate_pct": float(characterization.get("surface_fix_only_explained_rate_pct") or 0.0),
        "unresolved_explained_rate_pct": float(characterization.get("unresolved_explained_rate_pct") or 0.0),
        "profile_run_count": int(replay.get("profile_run_count") or 0),
        "unexplained_case_flip_count": int(replay.get("unexplained_case_flip_count") or 0),
        "per_case_outcome_consistency_rate_pct": float(replay.get("per_case_outcome_consistency_rate_pct") or 0.0),
        "workflow_resolution_rate_range_pct": float(replay.get("workflow_resolution_rate_range_pct") or 0.0),
        "goal_alignment_rate_range_pct": float(replay.get("goal_alignment_rate_range_pct") or 0.0),
    }
    integer_safe_equivalents = {
        "workflow_resolution_case_count": integer_safe_display(workflow_resolution_case_count, task_count),
        "goal_alignment_case_count": integer_safe_display(goal_alignment_case_count, task_count),
        "surface_fix_only_case_count": integer_safe_display(surface_fix_only_case_count, task_count),
        "unresolved_case_count": integer_safe_display(unresolved_case_count, task_count),
        "goal_artifact_missing_after_surface_fix_case_count": integer_safe_display(goal_artifact_case_count, task_count),
        "dispatch_or_policy_limited_case_count": integer_safe_display(dispatch_case_count, task_count),
        "workflow_spillover_case_count": integer_safe_display(spillover_case_count, task_count),
    }
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_threshold_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "frozen_baseline_metrics": metrics,
        "integer_safe_case_count_equivalents": integer_safe_equivalents,
        "frozen_barrier_distribution": barrier_distribution,
        "threshold_sensitivity_notes": {
            "supported_resolution_lift_needed": "Current baseline is 4/19; supported should start at or above 6/19.",
            "supported_goal_alignment_lift_needed": "Current baseline is 9/19; supported should start at or above 11/19.",
            "execution_posture_note": "Thresholds apply to the deterministic expanded-profile evidence model, not to live multi-run robustness claims.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.4 Threshold Input Table",
                "",
                f"- task_count: `{task_count}`",
                f"- workflow_resolution_case_count: `{workflow_resolution_case_count}`",
                f"- goal_alignment_case_count: `{goal_alignment_case_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.4 threshold input table.")
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v094_threshold_input_table(v093_closeout_path=str(args.v093_closeout), out_dir=str(args.out_dir))
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
