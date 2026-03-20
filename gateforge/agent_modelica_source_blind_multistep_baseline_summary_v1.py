from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_multi_round_baseline_summary_v1 import _executor_attempt_count, _ratio, _task_index, _write_json


SCHEMA_VERSION = "agent_modelica_source_blind_multistep_baseline_summary_v1"
ALLOWED_FAIL_BUCKETS = {
    "single_case_only",
    "stability_margin_miss",
    "behavior_contract_miss",
    "post_switch_recovery_miss",
    "scenario_switch_miss",
    "llm_patch_drift",
    "infra",
}
FAILURE_TYPE_TO_BUCKET = {
    "stability_then_behavior": "stability_margin_miss",
    "behavior_then_robustness": "single_case_only",
    "switch_then_recovery": "scenario_switch_miss",
}


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _scenario_results(record: dict) -> list[dict]:
    rows = record.get("scenario_results")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _all_scenarios_pass(record: dict) -> bool:
    rows = _scenario_results(record)
    if rows:
        return all(bool(row.get("pass")) for row in rows)
    return bool(record.get("contract_pass"))


def _partial_pass(record: dict) -> bool:
    rows = _scenario_results(record)
    if not rows:
        return False
    passes = [bool(row.get("pass")) for row in rows]
    return any(passes) and not all(passes)


def _infer_fail_bucket(record: dict, task: dict) -> str:
    if _partial_pass(record):
        return "single_case_only"
    bucket = str(record.get("contract_fail_bucket") or record.get("failure_bucket") or "").strip().lower()
    if bucket in ALLOWED_FAIL_BUCKETS:
        return bucket
    failure_type = str(task.get("failure_type") or "").strip().lower()
    return FAILURE_TYPE_TO_BUCKET.get(failure_type, "infra")


def _attempt_signature(attempt: dict, task: dict) -> str:
    stage = str(attempt.get("multi_step_stage") or "").strip().lower()
    if stage:
        return stage
    rows = attempt.get("scenario_results")
    if isinstance(rows, list) and rows:
        passes = [bool(row.get("pass")) for row in rows if isinstance(row, dict)]
        if passes and all(passes):
            return "all_scenarios_pass"
        if passes and any(passes):
            return "single_case_only"
    if bool(attempt.get("contract_pass")):
        return "all_scenarios_pass"
    bucket = str(attempt.get("contract_fail_bucket") or "").strip().lower()
    if bucket:
        return bucket
    reason = str(attempt.get("reason") or "").strip().lower()
    if reason:
        return reason
    observed = str(attempt.get("observed_failure_type") or "").strip().lower()
    if observed:
        return observed
    return FAILURE_TYPE_TO_BUCKET.get(str(task.get("failure_type") or "").strip().lower(), "infra")


def _repair_sequence(record: dict) -> list[str]:
    sequence: list[str] = []
    for attempt in [row for row in (record.get("attempts") or []) if isinstance(row, dict)]:
        local = attempt.get("source_blind_local_repair") if isinstance(attempt.get("source_blind_local_repair"), dict) else {}
        if local.get("applied"):
            cluster = str(local.get("cluster_name") or local.get("reason") or "").strip()
            if cluster:
                sequence.append(cluster)
                continue
        reason = str(attempt.get("reason") or "").strip()
        if reason:
            sequence.append(reason)
    return sequence


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize source-blind multi-step baseline results")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_source_blind_multistep_baseline_summary_v1/summary.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))
    task_map = _task_index(taskset)
    success_by_failure_type: dict[str, dict] = {}
    scenario_fail_by_failure_type: dict[str, dict] = {}
    scenario_fail_breakdown = {bucket: 0 for bucket in sorted(ALLOWED_FAIL_BUCKETS)}
    executor_attempt_values: list[float] = []
    all_scenarios_pass_count = 0
    partial_pass_count = 0
    failure_transition_count = 0
    distinct_failure_stages_seen_values: list[float] = []
    round_to_second_failure_values: list[float] = []
    multi_step_completion_count = 0
    stage_2_unlock_count = 0
    stage_2_then_fail_count = 0
    stage_2_then_pass_count = 0
    round_to_stage_2_values: list[float] = []
    round_from_stage_2_to_resolution_values: list[float] = []
    stage_2_focus_count = 0
    stage_1_revisit_after_unlock_count = 0
    stage_2_resolution_count = 0
    stage_plan_generated_count = 0
    stage_plan_followed_count = 0
    stage_2_plan_generated_count = 0
    stage_2_plan_followed_count = 0
    stage_2_plan_resolution_count = 0
    plan_conflict_rejected_count = 0
    repair_action_sequence: dict[str, int] = {}
    stage_transition_action_sequence: dict[str, int] = {}

    for record in [row for row in (baseline_results.get("records") or []) if isinstance(row, dict)]:
        task_id = str(record.get("task_id") or "").strip()
        task = task_map.get(task_id, {})
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        success_row = success_by_failure_type.setdefault(failure_type, {"task_count": 0, "success_count": 0})
        fail_row = scenario_fail_by_failure_type.setdefault(failure_type, {"task_count": 0, "scenario_fail_count": 0})
        success_row["task_count"] += 1
        fail_row["task_count"] += 1
        executor_attempt_values.append(float(_executor_attempt_count(record)))
        signatures: list[str] = []
        second_failure_round: int | None = None
        unlocked_rounds: list[int] = []
        stage_2_focus_seen = False
        stage_1_revisit_seen = False
        stage_plan_generated_seen = False
        stage_plan_followed_seen = False
        stage_2_plan_generated_seen = False
        stage_2_plan_followed_seen = False
        transition_focuses: list[str] = []
        for attempt in [row for row in (record.get("attempts") or []) if isinstance(row, dict)]:
            signature = _attempt_signature(attempt, task)
            if not signatures or signature != signatures[-1]:
                if signature not in signatures and signatures and second_failure_round is None:
                    second_failure_round = int(attempt.get("round") or 0)
                signatures.append(signature)
            if bool(attempt.get("multi_step_stage_2_unlocked")):
                try:
                    unlocked_rounds.append(max(0, int(attempt.get("multi_step_transition_round") or attempt.get("round") or 0)))
                except Exception:
                    pass
                focus = str(attempt.get("next_focus") or "").strip().lower()
                if focus:
                    transition_focuses.append(focus)
                current_stage = str(attempt.get("current_stage") or attempt.get("multi_step_stage") or "").strip().lower()
                if bool(attempt.get("stage_aware_control_applied")) and current_stage == "stage_2":
                    stage_2_focus_seen = True
                if bool(attempt.get("stage_1_revisit_after_unlock")):
                    stage_1_revisit_seen = True
            if bool(attempt.get("stage_plan_generated")):
                stage_plan_generated_seen = True
            if bool(attempt.get("stage_plan_followed")) or bool(attempt.get("plan_followed")):
                stage_plan_followed_seen = True
            if str(attempt.get("plan_stage") or "").strip().lower() == "stage_2":
                stage_2_plan_generated_seen = True
                if bool(attempt.get("stage_plan_followed")) or bool(attempt.get("plan_followed")):
                    stage_2_plan_followed_seen = True
            try:
                plan_conflict_rejected_count += max(0, int(attempt.get("plan_conflict_rejected_count") or 0))
            except Exception:
                pass
        if len(set(signatures)) > 1:
            failure_transition_count += 1
        distinct_failure_stages_seen_values.append(float(len(set(signatures or []))))
        if second_failure_round is not None:
            round_to_second_failure_values.append(float(second_failure_round))
        if stage_plan_generated_seen:
            stage_plan_generated_count += 1
        if stage_plan_followed_seen:
            stage_plan_followed_count += 1
        if stage_2_plan_generated_seen:
            stage_2_plan_generated_count += 1
        if stage_2_plan_followed_seen:
            stage_2_plan_followed_count += 1
        if unlocked_rounds:
            stage_2_unlock_count += 1
            first_unlock = min(x for x in unlocked_rounds if x > 0) if any(x > 0 for x in unlocked_rounds) else 0
            if first_unlock > 0:
                round_to_stage_2_values.append(float(first_unlock))
            if stage_2_focus_seen:
                stage_2_focus_count += 1
            if stage_1_revisit_seen:
                stage_1_revisit_after_unlock_count += 1
            if transition_focuses:
                key = " -> ".join(transition_focuses)
                stage_transition_action_sequence[key] = int(stage_transition_action_sequence.get(key, 0)) + 1
        if _all_scenarios_pass(record):
            all_scenarios_pass_count += 1
            if bool(record.get("multi_step_stage_2_unlocked")) or unlocked_rounds:
                stage_2_then_pass_count += 1
                stage_2_resolution_count += 1
                if stage_2_plan_followed_seen:
                    stage_2_plan_resolution_count += 1
                first_unlock = min(x for x in unlocked_rounds if x > 0) if any(x > 0 for x in unlocked_rounds) else 0
                if first_unlock > 0:
                    rounds_used = int(record.get("rounds_used") or len([row for row in (record.get("attempts") or []) if isinstance(row, dict)]) or 0)
                    if rounds_used >= first_unlock:
                        round_from_stage_2_to_resolution_values.append(float(rounds_used - first_unlock))
            if len(set(signatures)) > 1 or bool(record.get("multi_step_stage_2_unlocked")) or unlocked_rounds:
                multi_step_completion_count += 1
            if bool(record.get("passed")):
                success_row["success_count"] += 1
        else:
            if _partial_pass(record):
                partial_pass_count += 1
            if bool(record.get("multi_step_stage_2_unlocked")) or unlocked_rounds:
                stage_2_then_fail_count += 1
            fail_row["scenario_fail_count"] += 1
            bucket = _infer_fail_bucket(record, task)
            scenario_fail_breakdown[bucket] = int(scenario_fail_breakdown.get(bucket, 0)) + 1
        sequence = _repair_sequence(record)
        if sequence:
            key = " -> ".join(sequence)
            repair_action_sequence[key] = int(repair_action_sequence.get(key, 0)) + 1

    total_tasks = int(challenge.get("total_tasks") or len(task_map))
    for row in success_by_failure_type.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    for row in scenario_fail_by_failure_type.values():
        row["scenario_fail_pct"] = _ratio(int(row.get("scenario_fail_count") or 0), int(row.get("task_count") or 0))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": str(baseline_summary.get("status") or "FAIL"),
        "total_tasks": total_tasks,
        "success_count": int(baseline_summary.get("success_count") or 0),
        "success_at_k_pct": float(baseline_summary.get("success_at_k_pct") or 0.0),
        "all_scenarios_pass_count": all_scenarios_pass_count,
        "all_scenarios_pass_pct": _ratio(all_scenarios_pass_count, total_tasks),
        "partial_pass_count": partial_pass_count,
        "partial_pass_pct": _ratio(partial_pass_count, total_tasks),
        "scenario_fail_count": max(0, total_tasks - all_scenarios_pass_count),
        "scenario_fail_breakdown": scenario_fail_breakdown,
        "success_by_failure_type": success_by_failure_type,
        "scenario_fail_by_failure_type": scenario_fail_by_failure_type,
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_multistep_family": challenge.get("counts_by_multistep_family") if isinstance(challenge.get("counts_by_multistep_family"), dict) else {},
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "scenario_count_distribution": challenge.get("scenario_count_distribution") if isinstance(challenge.get("scenario_count_distribution"), dict) else {},
        "median_executor_attempts": round(_median(executor_attempt_values), 2),
        "failure_transition_count": failure_transition_count,
        "failure_transition_pct": _ratio(failure_transition_count, total_tasks),
        "median_distinct_failure_stages_seen": round(_median(distinct_failure_stages_seen_values), 2),
        "multi_step_completion_count": multi_step_completion_count,
        "multi_step_completion_pct": _ratio(multi_step_completion_count, total_tasks),
        "median_round_to_second_failure": round(_median(round_to_second_failure_values), 2),
        "stage_2_unlock_count": stage_2_unlock_count,
        "stage_2_unlock_pct": _ratio(stage_2_unlock_count, total_tasks),
        "median_round_to_stage_2": round(_median(round_to_stage_2_values), 2),
        "stage_2_then_fail_count": stage_2_then_fail_count,
        "stage_2_then_pass_count": stage_2_then_pass_count,
        "stage_2_focus_count": stage_2_focus_count,
        "stage_2_focus_pct": _ratio(stage_2_focus_count, total_tasks),
        "stage_1_revisit_after_unlock_count": stage_1_revisit_after_unlock_count,
        "stage_2_resolution_count": stage_2_resolution_count,
        "stage_plan_generated_count": stage_plan_generated_count,
        "stage_plan_generated_pct": _ratio(stage_plan_generated_count, total_tasks),
        "stage_plan_followed_count": stage_plan_followed_count,
        "stage_plan_followed_pct": _ratio(stage_plan_followed_count, total_tasks),
        "stage_2_plan_generated_count": stage_2_plan_generated_count,
        "stage_2_plan_generated_pct": _ratio(stage_2_plan_generated_count, total_tasks),
        "stage_2_plan_followed_count": stage_2_plan_followed_count,
        "stage_2_plan_followed_pct": _ratio(stage_2_plan_followed_count, total_tasks),
        "stage_2_plan_resolution_count": stage_2_plan_resolution_count,
        "plan_conflict_rejected_count": plan_conflict_rejected_count,
        "median_round_from_stage_2_to_resolution": round(_median(round_from_stage_2_to_resolution_values), 2),
        "repair_action_sequence": dict(sorted(repair_action_sequence.items(), key=lambda item: (-item[1], item[0]))[:10]),
        "stage_transition_action_sequence": dict(sorted(stage_transition_action_sequence.items(), key=lambda item: (-item[1], item[0]))[:10]),
        "multi_step_headroom_status": (
            "stage_aware_control_observed"
            if stage_2_plan_followed_count > 0
            else ("stage_aware_control_not_yet_effective" if stage_2_unlock_count > 0 else "task_construction_still_too_shallow")
        ),
        "sources": {
            "challenge_summary": args.challenge_summary,
            "baseline_summary": args.baseline_summary,
            "baseline_results": args.baseline_results,
        },
    }
    _write_json(args.out, summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "failure_transition_count": summary.get("failure_transition_count"),
                "multi_step_headroom_status": summary.get("multi_step_headroom_status"),
            }
        )
    )
    if str(summary.get("status")) == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
