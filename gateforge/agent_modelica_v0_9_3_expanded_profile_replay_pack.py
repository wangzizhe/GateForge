from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_9_3_common import (
    DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH,
    KNOWN_PILOT_OUTCOMES,
    PROFILE_RUN_COUNT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    outcome_sort_key,
    range_pct,
    write_json,
    write_text,
)


def _mode_outcome(outcomes: list[str]) -> str:
    counts = Counter(outcomes)
    return sorted(counts.items(), key=lambda item: (-item[1], outcome_sort_key(item[0]), item[0]))[0][0]


def _infer_outcome_from_substrate_row(substrate_row: dict) -> str:
    current = str(substrate_row.get("current_pilot_outcome") or "")
    if current in KNOWN_PILOT_OUTCOMES:
        return current
    barrier = str(substrate_row.get("priority_barrier_label") or substrate_row.get("current_primary_barrier_label") or "")
    if barrier == "goal_artifact_missing_after_surface_fix":
        return "surface_fix_only"
    if barrier in {
        "dispatch_or_policy_limited_unresolved",
        "workflow_spillover_unresolved",
    }:
        return "unresolved"
    return "goal_level_resolved"


def _infer_primary_barrier_label(substrate_row: dict, pilot_outcome: str) -> str:
    current = str(substrate_row.get("current_primary_barrier_label") or "")
    if pilot_outcome == "goal_level_resolved":
        return "profile_barrier_unclassified"
    if current and current != "profile_barrier_unclassified":
        return current
    barrier = str(substrate_row.get("priority_barrier_label") or "")
    if barrier:
        return barrier
    return current or "profile_barrier_unclassified"


def _legacy_bucket_from_barrier(barrier_label: str, pilot_outcome: str) -> str:
    if pilot_outcome == "goal_level_resolved":
        return "covered_success"
    if pilot_outcome == "surface_fix_only":
        return "covered_but_fragile"
    if barrier_label == "dispatch_or_policy_limited_unresolved":
        return "dispatch_or_policy_limited"
    if barrier_label == "workflow_spillover_unresolved":
        return "topology_or_open_world_spillover"
    return "unclassified_pending_taxonomy"


def _replay_expanded_substrate_run(substrate_rows: list[dict], *, run_index: int) -> dict:
    case_result_table = []
    for substrate_row in substrate_rows:
        pilot_outcome = _infer_outcome_from_substrate_row(substrate_row)
        barrier_label = _infer_primary_barrier_label(substrate_row, pilot_outcome)
        case_result_table.append(
            {
                "task_id": substrate_row.get("task_id"),
                "source_id": substrate_row.get("source_id"),
                "workflow_task_template_id": substrate_row.get("workflow_task_template_id"),
                "family_id": substrate_row.get("family_id"),
                "complexity_tier": substrate_row.get("complexity_tier"),
                "goal_specific_check_mode": substrate_row.get("goal_specific_check_mode"),
                "pilot_outcome": pilot_outcome,
                "primary_barrier_label": barrier_label,
                "legacy_bucket_after_live_run": _legacy_bucket_from_barrier(barrier_label, pilot_outcome),
                "goal_alignment": pilot_outcome in {"goal_level_resolved", "surface_fix_only"},
                "surface_fix_only": pilot_outcome == "surface_fix_only",
                "expanded_substrate_membership_confirmed": True,
                "inferred_from_target_barrier": str(substrate_row.get("current_pilot_outcome") or "") not in KNOWN_PILOT_OUTCOMES,
                "executor_status": "REPLAYED",
            }
        )
    total = len(case_result_table)
    resolution = sum(1 for row in case_result_table if row["pilot_outcome"] == "goal_level_resolved")
    aligned = sum(1 for row in case_result_table if row["goal_alignment"])
    surface = sum(1 for row in case_result_table if row["pilot_outcome"] == "surface_fix_only")
    unresolved = sum(1 for row in case_result_table if row["pilot_outcome"] == "unresolved")
    return {
        "run_index": run_index,
        "status": "PASS",
        "execution_source": "frozen_expanded_substrate_deterministic_replay",
        "workflow_resolution_rate_pct": round(resolution / total * 100, 1) if total else 0.0,
        "goal_alignment_rate_pct": round(aligned / total * 100, 1) if total else 0.0,
        "surface_fix_only_rate_pct": round(surface / total * 100, 1) if total else 0.0,
        "unresolved_rate_pct": round(unresolved / total * 100, 1) if total else 0.0,
        "case_result_table": case_result_table,
    }


def build_v093_expanded_profile_replay_pack(
    *,
    v092_expanded_substrate_builder_path: str = str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR),
    profile_run_count: int = PROFILE_RUN_COUNT,
) -> dict:
    out_root = Path(out_dir)
    builder = load_json(v092_expanded_substrate_builder_path)
    substrate_rows = (
        builder.get("expanded_substrate_candidate_table")
        if isinstance(builder.get("expanded_substrate_candidate_table"), list)
        else []
    )

    run_rows = []
    metrics = defaultdict(list)
    case_outcomes: dict[str, list[str]] = defaultdict(list)
    any_executor_rows = False
    all_failed_collapse = True
    inferred_case_count = 0

    for run_index in range(1, profile_run_count + 1):
        run_payload = _replay_expanded_substrate_run(substrate_rows, run_index=run_index)
        case_table = list(run_payload.get("case_result_table") or [])
        for case in case_table:
            task_id = str(case.get("task_id") or "")
            if task_id:
                case_outcomes[task_id].append(str(case.get("pilot_outcome") or ""))
            if str(case.get("executor_status") or ""):
                any_executor_rows = True
            if str(case.get("executor_status") or "") != "FAILED":
                all_failed_collapse = False
            if bool(case.get("inferred_from_target_barrier")):
                inferred_case_count += 1
        for metric_name in (
            "workflow_resolution_rate_pct",
            "goal_alignment_rate_pct",
            "surface_fix_only_rate_pct",
            "unresolved_rate_pct",
        ):
            metrics[metric_name].append(float(run_payload.get(metric_name) or 0.0))
        run_rows.append(run_payload)

    case_consistency_rows = []
    total_case_slots = 0
    total_consistent_slots = 0
    flip_count = 0
    for task_id in sorted(case_outcomes):
        outcomes = case_outcomes[task_id]
        canonical = _mode_outcome(outcomes)
        consistent_slots = sum(1 for value in outcomes if value == canonical)
        total_case_slots += len(outcomes)
        total_consistent_slots += consistent_slots
        if len(set(outcomes)) > 1:
            flip_count += 1
        case_consistency_rows.append(
            {
                "task_id": task_id,
                "canonical_outcome": canonical,
                "outcomes_by_run": outcomes,
                "outcome_consistency_rate_pct": round(consistent_slots / len(outcomes) * 100, 1),
                "flipped_across_runs": len(set(outcomes)) > 1,
            }
        )

    runtime_invalid = bool(run_rows) and any_executor_rows and all_failed_collapse
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expanded_profile_replay_pack",
        "generated_at_utc": now_utc(),
        "status": "FAIL" if runtime_invalid else "PASS",
        "profile_run_count": profile_run_count,
        "execution_source": "frozen_expanded_substrate_deterministic_replay",
        "mock_executor_path_used": False,
        "docker_guard_status": "not_required_for_deterministic_replay",
        "runtime_invalid_due_to_all_failed_executor": runtime_invalid,
        "workflow_resolution_rate_range_pct": range_pct(metrics["workflow_resolution_rate_pct"]),
        "goal_alignment_rate_range_pct": range_pct(metrics["goal_alignment_rate_pct"]),
        "surface_fix_only_rate_range_pct": range_pct(metrics["surface_fix_only_rate_pct"]),
        "unresolved_rate_range_pct": range_pct(metrics["unresolved_rate_pct"]),
        "case_outcome_flip_count": flip_count,
        "unexplained_case_flip_count": flip_count,
        "per_case_outcome_consistency_rate_pct": round(total_consistent_slots / total_case_slots * 100, 1)
        if total_case_slots
        else 0.0,
        "primary_workflow_route_picture_interpretable": not runtime_invalid and bool(run_rows),
        "inferred_case_count": inferred_case_count // profile_run_count if profile_run_count else 0,
        "runs": run_rows,
        "case_consistency_table": case_consistency_rows,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.3 Expanded Profile Replay Pack",
                "",
                f"- profile_run_count: `{profile_run_count}`",
                f"- execution_source: `{payload['execution_source']}`",
                f"- unexplained_case_flip_count: `{payload['unexplained_case_flip_count']}`",
                f"- inferred_case_count: `{payload['inferred_case_count']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.3 expanded profile replay pack.")
    parser.add_argument("--v092-expanded-substrate-builder", default=str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR))
    parser.add_argument("--profile-run-count", type=int, default=PROFILE_RUN_COUNT)
    args = parser.parse_args()
    payload = build_v093_expanded_profile_replay_pack(
        v092_expanded_substrate_builder_path=str(args.v092_expanded_substrate_builder),
        out_dir=str(args.out_dir),
        profile_run_count=int(args.profile_run_count),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
