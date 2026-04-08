from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_2_common import (
    DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR,
    DEFAULT_V081_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    count_from_pct,
    load_json,
    now_utc,
    share_pct,
    write_json,
    write_text,
)


def build_v082_threshold_input_table(
    *,
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR),
) -> dict:
    closeout = load_json(v081_closeout_path)
    replay = closeout.get("profile_replay_pack") or {}
    characterization = closeout.get("workflow_profile_characterization") or {}

    task_count = int(len(characterization.get("case_characterization_table") or []))
    barrier_distribution = characterization.get("barrier_label_distribution") or {}
    goal_artifact_count = int(barrier_distribution.get("goal_artifact_missing_after_surface_fix", 0))
    dispatch_count = int(barrier_distribution.get("dispatch_or_policy_limited_unresolved", 0))
    spillover_count = int(barrier_distribution.get("workflow_spillover_unresolved", 0))

    legacy_crosswalk = characterization.get("legacy_bucket_crosswalk_by_outcome") or {}
    unresolved_crosswalk = legacy_crosswalk.get("unresolved") or {}
    legacy_mapping_rate_pct = 100.0 - share_pct(
        int(characterization.get("profile_barrier_unclassified_count") or 0), task_count
    )

    metrics = {
        "task_count": task_count,
        "workflow_resolution_rate_pct": float(replay.get("runs", [{}])[0].get("workflow_resolution_rate_pct") or 0.0)
        if replay.get("runs")
        else 0.0,
        "goal_alignment_rate_pct": float(replay.get("runs", [{}])[0].get("goal_alignment_rate_pct") or 0.0)
        if replay.get("runs")
        else 0.0,
        "surface_fix_only_rate_pct": float(replay.get("runs", [{}])[0].get("surface_fix_only_rate_pct") or 0.0)
        if replay.get("runs")
        else 0.0,
        "unresolved_rate_pct": float(replay.get("runs", [{}])[0].get("unresolved_rate_pct") or 0.0)
        if replay.get("runs")
        else 0.0,
        "workflow_spillover_share_pct": share_pct(spillover_count, task_count),
        "dispatch_or_policy_limited_share_pct": share_pct(dispatch_count, task_count),
        "goal_artifact_missing_after_surface_fix_share_pct": share_pct(goal_artifact_count, task_count),
        "profile_barrier_unclassified_count": int(characterization.get("profile_barrier_unclassified_count") or 0),
        "barrier_label_coverage_rate_pct": float(characterization.get("barrier_label_coverage_rate_pct") or 0.0),
        "surface_fix_only_explained_rate_pct": float(
            characterization.get("surface_fix_only_explained_rate_pct") or 0.0
        ),
        "unresolved_explained_rate_pct": float(
            characterization.get("unresolved_explained_rate_pct") or 0.0
        ),
        "legacy_bucket_mapping_rate_pct": legacy_mapping_rate_pct,
        "profile_run_count": int(replay.get("profile_run_count") or 0),
        "workflow_resolution_rate_range_pct": float(
            replay.get("workflow_resolution_rate_range_pct") or 0.0
        ),
        "goal_alignment_rate_range_pct": float(replay.get("goal_alignment_rate_range_pct") or 0.0),
        "per_case_outcome_consistency_rate_pct": float(
            replay.get("per_case_outcome_consistency_rate_pct") or 0.0
        ),
    }
    integer_safe_equivalents = {
        key: count_from_pct(value, task_count)
        for key, value in metrics.items()
        if key.endswith("_pct")
    }
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_threshold_input_table",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "frozen_baseline_metrics": metrics,
        "integer_safe_case_count_equivalents": integer_safe_equivalents,
        "frozen_barrier_distribution": barrier_distribution,
        "frozen_legacy_unresolved_crosswalk": unresolved_crosswalk,
        "threshold_sensitivity_notes": {
            "workflow_resolution_delta_needed_for_supported": "At least +10.0pp over the current 40.0 baseline.",
            "spillover_upper_bound_before_unbounded_picture": "Above 30.0% should push the picture toward fallback.",
            "surface_fix_only_interpretation": "20.0% is tolerated for partial but should not dominate a supported picture.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.2 Threshold Input Table",
                "",
                f"- task_count: `{task_count}`",
                f"- workflow_resolution_rate_pct: `{metrics['workflow_resolution_rate_pct']}`",
                f"- workflow_spillover_share_pct: `{metrics['workflow_spillover_share_pct']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.2 threshold input table.")
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v082_threshold_input_table(
        v081_closeout_path=str(args.v081_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
