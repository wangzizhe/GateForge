from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .agent_modelica_behavioral_robustness_baseline_summary_v1 import _load_json
from .agent_modelica_multi_round_evidence_v1 import _task_index, _write_json


SCHEMA_VERSION = "agent_modelica_source_blind_multistep_evidence_v1"


def _scenario_results(record: dict) -> list[dict]:
    rows = record.get("scenario_results")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _record_all_scenarios_pass(record: dict) -> bool:
    rows = _scenario_results(record)
    if rows:
        return all(bool(row.get("pass")) for row in rows)
    return bool(record.get("contract_pass"))


def _record_partial_pass(record: dict) -> bool:
    rows = _scenario_results(record)
    if not rows:
        return False
    passes = [bool(row.get("pass")) for row in rows]
    return any(passes) and not all(passes)


def _partial_to_full(taskset_payload: dict, baseline_results: dict, deterministic_results: dict) -> tuple[int, dict[str, dict]]:
    task_map = _task_index(taskset_payload)
    baseline_map = {
        str(row.get("task_id") or "").strip(): row
        for row in (baseline_results.get("records") or [])
        if isinstance(row, dict) and str(row.get("task_id") or "").strip()
    }
    deterministic_map = {
        str(row.get("task_id") or "").strip(): row
        for row in (deterministic_results.get("records") or [])
        if isinstance(row, dict) and str(row.get("task_id") or "").strip()
    }
    total_count = 0
    by_failure_type: dict[str, dict] = {}
    for task_id, det_record in deterministic_map.items():
        base_record = baseline_map.get(task_id, {})
        if not _record_partial_pass(base_record):
            continue
        total_count += 1 if _record_all_scenarios_pass(det_record) else 0
        failure_type = str((task_map.get(task_id) or {}).get("failure_type") or "unknown").strip().lower()
        row = by_failure_type.setdefault(failure_type, {"task_count": 0, "partial_to_full_count": 0})
        row["task_count"] += 1
        if _record_all_scenarios_pass(det_record):
            row["partial_to_full_count"] += 1
    for row in by_failure_type.values():
        task_count = int(row.get("task_count") or 0)
        row["partial_to_full_pct"] = round((int(row.get("partial_to_full_count") or 0) / task_count) * 100.0, 2) if task_count > 0 else 0.0
    return total_count, by_failure_type


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize source-blind multi-step evidence")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--deterministic-summary", required=True)
    parser.add_argument("--deterministic-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_source_blind_multistep_evidence_v1/evidence.json")
    parser.add_argument("--gate-out", default="artifacts/agent_modelica_source_blind_multistep_evidence_v1/gate.json")
    parser.add_argument("--decision-out", default="artifacts/agent_modelica_source_blind_multistep_evidence_v1/decision.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    deterministic_summary = _load_json(args.deterministic_summary)
    deterministic_results = _load_json(args.deterministic_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))

    baseline_pct = float(baseline_summary.get("all_scenarios_pass_pct") or 0.0)
    deterministic_pct = float(
        deterministic_summary.get("all_scenarios_pass_pct")
        or deterministic_summary.get("contract_pass_pct")
        or deterministic_summary.get("success_at_k_pct")
        or 0.0
    )
    baseline_partial_pct = float(baseline_summary.get("partial_pass_pct") or 0.0)
    transition_count = int(baseline_summary.get("failure_transition_count") or 0)
    stage_2_unlock_count = int(baseline_summary.get("stage_2_unlock_count") or 0)
    stage_2_focus_count = int(baseline_summary.get("stage_2_focus_count") or 0)
    stage_1_revisit_after_unlock_count = int(baseline_summary.get("stage_1_revisit_after_unlock_count") or 0)
    stage_2_resolution_count = int(baseline_summary.get("stage_2_resolution_count") or 0)
    stage_2_resolution_pct = float(baseline_summary.get("stage_2_resolution_pct") or 0.0)
    stage_2_resolution_by_failure_type = (
        baseline_summary.get("stage_2_resolution_by_failure_type")
        if isinstance(baseline_summary.get("stage_2_resolution_by_failure_type"), dict)
        else {}
    )
    stage_plan_generated_count = int(baseline_summary.get("stage_plan_generated_count") or 0)
    stage_plan_followed_count = int(baseline_summary.get("stage_plan_followed_count") or 0)
    stage_2_plan_generated_count = int(baseline_summary.get("stage_2_plan_generated_count") or 0)
    stage_2_plan_followed_count = int(baseline_summary.get("stage_2_plan_followed_count") or 0)
    stage_2_plan_resolution_count = int(baseline_summary.get("stage_2_plan_resolution_count") or 0)
    plan_conflict_rejected_count = int(baseline_summary.get("plan_conflict_rejected_count") or 0)
    local_search_attempt_count = int(baseline_summary.get("local_search_attempt_count") or 0)
    local_search_success_count = int(baseline_summary.get("local_search_success_count") or 0)
    local_search_success_pct = float(baseline_summary.get("local_search_success_pct") or 0.0)
    adaptive_search_attempt_count = int(baseline_summary.get("adaptive_search_attempt_count") or 0)
    adaptive_search_success_count = int(baseline_summary.get("adaptive_search_success_count") or 0)
    adaptive_search_success_pct = float(baseline_summary.get("adaptive_search_success_pct") or 0.0)
    stage_1_unlock_via_local_search_count = int(baseline_summary.get("stage_1_unlock_via_local_search_count") or 0)
    stage_2_resolution_via_local_search_count = int(baseline_summary.get("stage_2_resolution_via_local_search_count") or 0)
    cluster_only_resolution_count = int(baseline_summary.get("cluster_only_resolution_count") or 0)
    stage_1_unlock_via_adaptive_search_count = int(baseline_summary.get("stage_1_unlock_via_adaptive_search_count") or 0)
    stage_2_resolution_via_adaptive_search_count = int(baseline_summary.get("stage_2_resolution_via_adaptive_search_count") or 0)
    template_only_resolution_count = int(baseline_summary.get("template_only_resolution_count") or 0)
    adaptive_vs_template_resolution_split = baseline_summary.get("adaptive_vs_template_resolution_split") if isinstance(baseline_summary.get("adaptive_vs_template_resolution_split"), dict) else {}
    stage_2_hard_case_count = int(baseline_summary.get("stage_2_hard_case_count") or 0)
    stage_2_hard_case_resolution_count = int(baseline_summary.get("stage_2_hard_case_resolution_count") or 0)
    stage_2_hard_case_resolution_pct = float(baseline_summary.get("stage_2_hard_case_resolution_pct") or 0.0)
    search_bad_direction_count = int(baseline_summary.get("search_bad_direction_count") or 0)
    stage_2_branch_count = int(baseline_summary.get("stage_2_branch_count") or 0)
    stage_2_branch_pct = float(baseline_summary.get("stage_2_branch_pct") or 0.0)
    branch_selection_error_count = int(baseline_summary.get("branch_selection_error_count") or 0)
    good_branch_resolution_count = int(baseline_summary.get("good_branch_resolution_count") or 0)
    trap_branch_enter_count = int(baseline_summary.get("trap_branch_enter_count") or 0)
    trap_branch_recovery_count = int(baseline_summary.get("trap_branch_recovery_count") or 0)
    trap_escape_success_count = int(baseline_summary.get("trap_escape_success_count") or 0)
    trap_branch_resolution_count = int(baseline_summary.get("trap_branch_resolution_count") or 0)
    trap_branch_resolution_pct = float(baseline_summary.get("trap_branch_resolution_pct") or 0.0)
    preferred_branch_resolution_count = int(baseline_summary.get("preferred_branch_resolution_count") or 0)
    wrong_branch_enter_count = int(baseline_summary.get("wrong_branch_enter_count") or 0)
    wrong_branch_recovery_count = int(baseline_summary.get("wrong_branch_recovery_count") or 0)
    branch_escape_attempt_count = int(baseline_summary.get("branch_escape_attempt_count") or 0)
    branch_escape_success_count = int(baseline_summary.get("branch_escape_success_count") or 0)
    branch_escape_success_pct = float(baseline_summary.get("branch_escape_success_pct") or 0.0)
    branch_budget_reallocated_count = int(baseline_summary.get("branch_budget_reallocated_count") or 0)
    repeated_trap_branch_count = int(baseline_summary.get("repeated_trap_branch_count") or 0)
    median_round_to_correct_branch = float(baseline_summary.get("median_round_to_correct_branch") or 0.0)
    hard_case_remaining_buckets = baseline_summary.get("hard_case_remaining_buckets") if isinstance(baseline_summary.get("hard_case_remaining_buckets"), dict) else {}
    llm_request_count_total = int(baseline_summary.get("llm_request_count_total") or 0)
    llm_task_count = int(baseline_summary.get("llm_task_count") or 0)
    planner_backend_counts = baseline_summary.get("planner_backend_counts") if isinstance(baseline_summary.get("planner_backend_counts"), dict) else {}
    resolved_llm_provider_counts = baseline_summary.get("resolved_llm_provider_counts") if isinstance(baseline_summary.get("resolved_llm_provider_counts"), dict) else {}
    planner_family_counts = baseline_summary.get("planner_family_counts") if isinstance(baseline_summary.get("planner_family_counts"), dict) else {}
    planner_adapter_counts = baseline_summary.get("planner_adapter_counts") if isinstance(baseline_summary.get("planner_adapter_counts"), dict) else {}
    llm_plan_task_count = int(baseline_summary.get("llm_plan_task_count") or 0)
    llm_plan_followed_count = int(baseline_summary.get("llm_plan_followed_count") or 0)
    llm_plan_branch_match_count = int(baseline_summary.get("llm_plan_branch_match_count") or 0)
    first_plan_branch_match_count = int(baseline_summary.get("first_plan_branch_match_count") or 0)
    replan_branch_match_count = int(baseline_summary.get("replan_branch_match_count") or 0)
    llm_plan_helped_resolution_count = int(baseline_summary.get("llm_plan_helped_resolution_count") or 0)
    llm_plan_was_decisive_count = int(baseline_summary.get("llm_plan_was_decisive_count") or 0)
    llm_called_only_count = int(baseline_summary.get("llm_called_only_count") or 0)
    llm_plan_failure_modes = baseline_summary.get("llm_plan_failure_modes") if isinstance(baseline_summary.get("llm_plan_failure_modes"), dict) else {}
    llm_replan_task_count = int(baseline_summary.get("llm_replan_task_count") or 0)
    llm_replan_used_count = int(baseline_summary.get("llm_replan_used_count") or 0)
    llm_replan_resolution_count = int(baseline_summary.get("llm_replan_resolution_count") or 0)
    llm_second_replan_used_count = int(baseline_summary.get("llm_second_replan_used_count") or 0)
    llm_second_replan_resolution_count = int(baseline_summary.get("llm_second_replan_resolution_count") or 0)
    first_plan_resolution_count = int(baseline_summary.get("first_plan_resolution_count") or 0)
    replan_after_branch_miss_count = int(baseline_summary.get("replan_after_branch_miss_count") or 0)
    backtracking_used_count = int(baseline_summary.get("backtracking_used_count") or 0)
    llm_guided_search_used_count = int(baseline_summary.get("llm_guided_search_used_count") or 0)
    search_budget_from_llm_plan_avg = float(baseline_summary.get("search_budget_from_llm_plan_avg") or 0.0)
    search_budget_followed_count = int(baseline_summary.get("search_budget_followed_count") or 0)
    llm_budget_helped_resolution_count = int(baseline_summary.get("llm_budget_helped_resolution_count") or 0)
    llm_guided_search_resolution_count = int(baseline_summary.get("llm_guided_search_resolution_count") or 0)
    llm_replan_budget_consumed_avg = float(baseline_summary.get("llm_replan_budget_consumed_avg") or 0.0)
    llm_replan_switch_branch_count = int(baseline_summary.get("llm_replan_switch_branch_count") or 0)
    llm_replan_same_branch_success_count = int(baseline_summary.get("llm_replan_same_branch_success_count") or 0)
    llm_replan_switch_branch_success_count = int(baseline_summary.get("llm_replan_switch_branch_success_count") or 0)
    llm_replan_budget_efficiency = float(baseline_summary.get("llm_replan_budget_efficiency") or 0.0)
    abandoned_branch_count = int(baseline_summary.get("abandoned_branch_count") or 0)
    budget_wasted_on_bad_branch_count = int(baseline_summary.get("budget_wasted_on_bad_branch_count") or 0)
    llm_resolution_count = int(baseline_summary.get("llm_resolution_count") or 0)
    llm_only_resolution_count = int(baseline_summary.get("llm_only_resolution_count") or 0)
    llm_branch_correction_count = int(baseline_summary.get("llm_branch_correction_count") or 0)
    llm_usage_by_failure_type = baseline_summary.get("llm_usage_by_failure_type") if isinstance(baseline_summary.get("llm_usage_by_failure_type"), dict) else {}
    llm_usage_by_branch = baseline_summary.get("llm_usage_by_branch") if isinstance(baseline_summary.get("llm_usage_by_branch"), dict) else {}
    deterministic_vs_llm_resolution_split = baseline_summary.get("deterministic_vs_llm_resolution_split") if isinstance(baseline_summary.get("deterministic_vs_llm_resolution_split"), dict) else {}
    deterministic_vs_first_plan_vs_replan_split = baseline_summary.get("deterministic_vs_first_plan_vs_replan_split") if isinstance(baseline_summary.get("deterministic_vs_first_plan_vs_replan_split"), dict) else {}
    partial_to_full_count, partial_to_full_by_failure = _partial_to_full(taskset, baseline_results, deterministic_results)
    task_total = int(challenge.get("total_tasks") or 0)
    partial_to_full_pct = round((partial_to_full_count / task_total) * 100.0, 2) if task_total > 0 else 0.0
    deterministic_uplift_status = "observed" if deterministic_pct > baseline_pct or partial_to_full_count > 0 else "not_observed"
    stage_aware_control_status = "stage_aware_control_observed" if stage_2_plan_followed_count > 0 else "stage_aware_control_not_yet_effective"
    primary_reason = "deterministic_uplift_observed" if deterministic_uplift_status == "observed" else stage_aware_control_status
    decision = "promote" if deterministic_uplift_status == "observed" else "needs_review"

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if decision == "promote" else "NEEDS_REVIEW",
        "all_scenarios_pass": {
            "baseline_pct": baseline_pct,
            "deterministic_pct": deterministic_pct,
            "deterministic_delta_pp": round(deterministic_pct - baseline_pct, 2),
        },
        "partial_pass_pct": baseline_partial_pct,
        "failure_transition_count": transition_count,
        "stage_2_unlock_count": stage_2_unlock_count,
        "stage_2_unlock_pct": float(baseline_summary.get("stage_2_unlock_pct") or 0.0),
        "median_round_to_stage_2": float(baseline_summary.get("median_round_to_stage_2") or 0.0),
        "stage_2_then_fail_count": int(baseline_summary.get("stage_2_then_fail_count") or 0),
        "stage_2_then_pass_count": int(baseline_summary.get("stage_2_then_pass_count") or 0),
        "stage_2_focus_count": stage_2_focus_count,
        "stage_2_focus_pct": float(baseline_summary.get("stage_2_focus_pct") or 0.0),
        "stage_1_revisit_after_unlock_count": stage_1_revisit_after_unlock_count,
        "stage_2_resolution_count": stage_2_resolution_count,
        "stage_2_resolution_pct": stage_2_resolution_pct,
        "stage_2_resolution_by_failure_type": stage_2_resolution_by_failure_type,
        "stage_plan_generated_count": stage_plan_generated_count,
        "stage_plan_generated_pct": float(baseline_summary.get("stage_plan_generated_pct") or 0.0),
        "stage_plan_followed_count": stage_plan_followed_count,
        "stage_plan_followed_pct": float(baseline_summary.get("stage_plan_followed_pct") or 0.0),
        "stage_2_plan_generated_count": stage_2_plan_generated_count,
        "stage_2_plan_generated_pct": float(baseline_summary.get("stage_2_plan_generated_pct") or 0.0),
        "stage_2_plan_followed_count": stage_2_plan_followed_count,
        "stage_2_plan_followed_pct": float(baseline_summary.get("stage_2_plan_followed_pct") or 0.0),
        "stage_2_plan_resolution_count": stage_2_plan_resolution_count,
        "plan_conflict_rejected_count": plan_conflict_rejected_count,
        "local_search_attempt_count": local_search_attempt_count,
        "local_search_success_count": local_search_success_count,
        "local_search_success_pct": local_search_success_pct,
        "adaptive_search_attempt_count": adaptive_search_attempt_count,
        "adaptive_search_success_count": adaptive_search_success_count,
        "adaptive_search_success_pct": adaptive_search_success_pct,
        "stage_1_unlock_via_local_search_count": stage_1_unlock_via_local_search_count,
        "stage_2_resolution_via_local_search_count": stage_2_resolution_via_local_search_count,
        "cluster_only_resolution_count": cluster_only_resolution_count,
        "stage_1_unlock_via_adaptive_search_count": stage_1_unlock_via_adaptive_search_count,
        "stage_2_resolution_via_adaptive_search_count": stage_2_resolution_via_adaptive_search_count,
        "template_only_resolution_count": template_only_resolution_count,
        "adaptive_vs_template_resolution_split": adaptive_vs_template_resolution_split,
        "stage_2_hard_case_count": stage_2_hard_case_count,
        "stage_2_hard_case_resolution_count": stage_2_hard_case_resolution_count,
        "stage_2_hard_case_resolution_pct": stage_2_hard_case_resolution_pct,
        "search_bad_direction_count": search_bad_direction_count,
        "stage_2_branch_count": stage_2_branch_count,
        "stage_2_branch_pct": stage_2_branch_pct,
        "branch_selection_error_count": branch_selection_error_count,
        "good_branch_resolution_count": good_branch_resolution_count,
        "trap_branch_enter_count": trap_branch_enter_count,
        "trap_branch_recovery_count": trap_branch_recovery_count,
        "trap_branch_resolution_count": trap_branch_resolution_count,
        "trap_branch_resolution_pct": trap_branch_resolution_pct,
        "preferred_branch_resolution_count": preferred_branch_resolution_count,
        "branch_escape_attempt_count": branch_escape_attempt_count,
        "branch_escape_success_count": branch_escape_success_count,
        "branch_escape_success_pct": branch_escape_success_pct,
        "branch_budget_reallocated_count": branch_budget_reallocated_count,
        "repeated_trap_branch_count": repeated_trap_branch_count,
        "repeated_bad_branch_count": repeated_trap_branch_count,
        "trap_escape_success_count": trap_escape_success_count,
        "wrong_branch_enter_count": wrong_branch_enter_count,
        "wrong_branch_recovery_count": wrong_branch_recovery_count,
        "llm_request_count_total": llm_request_count_total,
        "llm_task_count": llm_task_count,
        "planner_backend_counts": planner_backend_counts,
        "resolved_llm_provider_counts": resolved_llm_provider_counts,
        "planner_family_counts": planner_family_counts,
        "planner_adapter_counts": planner_adapter_counts,
        "llm_plan_task_count": llm_plan_task_count,
        "llm_plan_followed_count": llm_plan_followed_count,
        "llm_plan_followed_pct": float(baseline_summary.get("llm_plan_followed_pct") or 0.0),
        "llm_plan_branch_match_count": llm_plan_branch_match_count,
        "llm_plan_branch_match_pct": float(baseline_summary.get("llm_plan_branch_match_pct") or 0.0),
        "first_plan_branch_match_count": first_plan_branch_match_count,
        "first_plan_branch_match_pct": float(baseline_summary.get("first_plan_branch_match_pct") or 0.0),
        "replan_branch_match_count": replan_branch_match_count,
        "replan_branch_match_pct": float(baseline_summary.get("replan_branch_match_pct") or 0.0),
        "llm_plan_helped_resolution_count": llm_plan_helped_resolution_count,
        "llm_plan_helped_resolution_pct": float(baseline_summary.get("llm_plan_helped_resolution_pct") or 0.0),
        "llm_plan_was_decisive_count": llm_plan_was_decisive_count,
        "llm_called_only_count": llm_called_only_count,
        "llm_plan_failure_modes": llm_plan_failure_modes,
        "llm_replan_task_count": llm_replan_task_count,
        "llm_replan_used_count": llm_replan_used_count,
        "llm_replan_used_pct": float(baseline_summary.get("llm_replan_used_pct") or 0.0),
        "llm_replan_resolution_count": llm_replan_resolution_count,
        "llm_replan_resolution_pct": float(baseline_summary.get("llm_replan_resolution_pct") or 0.0),
        "llm_second_replan_used_count": llm_second_replan_used_count,
        "llm_second_replan_used_pct": float(baseline_summary.get("llm_second_replan_used_pct") or 0.0),
        "llm_second_replan_resolution_count": llm_second_replan_resolution_count,
        "llm_second_replan_resolution_pct": float(baseline_summary.get("llm_second_replan_resolution_pct") or 0.0),
        "first_plan_resolution_count": first_plan_resolution_count,
        "replan_after_branch_miss_count": replan_after_branch_miss_count,
        "backtracking_used_count": backtracking_used_count,
        "llm_guided_search_used_count": llm_guided_search_used_count,
        "llm_guided_search_used_pct": float(baseline_summary.get("llm_guided_search_used_pct") or 0.0),
        "search_budget_from_llm_plan_avg": search_budget_from_llm_plan_avg,
        "search_budget_followed_count": search_budget_followed_count,
        "search_budget_followed_pct": float(baseline_summary.get("search_budget_followed_pct") or 0.0),
        "llm_budget_helped_resolution_count": llm_budget_helped_resolution_count,
        "llm_budget_helped_resolution_pct": float(baseline_summary.get("llm_budget_helped_resolution_pct") or 0.0),
        "llm_guided_search_resolution_count": llm_guided_search_resolution_count,
        "llm_replan_budget_consumed_avg": llm_replan_budget_consumed_avg,
        "llm_replan_switch_branch_count": llm_replan_switch_branch_count,
        "llm_replan_same_branch_success_count": llm_replan_same_branch_success_count,
        "llm_replan_switch_branch_success_count": llm_replan_switch_branch_success_count,
        "llm_replan_budget_efficiency": llm_replan_budget_efficiency,
        "abandoned_branch_count": abandoned_branch_count,
        "budget_wasted_on_bad_branch_count": budget_wasted_on_bad_branch_count,
        "llm_resolution_count": llm_resolution_count,
        "llm_only_resolution_count": llm_only_resolution_count,
        "llm_branch_correction_count": llm_branch_correction_count,
        "llm_usage_by_failure_type": llm_usage_by_failure_type,
        "llm_usage_by_branch": llm_usage_by_branch,
        "deterministic_vs_llm_resolution_split": deterministic_vs_llm_resolution_split,
        "deterministic_vs_first_plan_vs_replan_split": deterministic_vs_first_plan_vs_replan_split,
        "median_round_to_correct_branch": median_round_to_correct_branch,
        "hard_case_remaining_buckets": hard_case_remaining_buckets,
        "median_round_from_stage_2_to_resolution": float(baseline_summary.get("median_round_from_stage_2_to_resolution") or 0.0),
        "multi_step_completion_count": int(baseline_summary.get("multi_step_completion_count") or 0),
        "median_round_to_second_failure": float(baseline_summary.get("median_round_to_second_failure") or 0.0),
        "repair_action_sequence": baseline_summary.get("repair_action_sequence") if isinstance(baseline_summary.get("repair_action_sequence"), dict) else {},
        "stage_transition_action_sequence": baseline_summary.get("stage_transition_action_sequence") if isinstance(baseline_summary.get("stage_transition_action_sequence"), dict) else {},
        "deterministic_partial_to_full_count": partial_to_full_count,
        "deterministic_partial_to_full_pct": partial_to_full_pct,
        "deterministic_by_failure_type": partial_to_full_by_failure,
        "deterministic_uplift_status": deterministic_uplift_status,
        "stage_aware_control_status": stage_aware_control_status,
        "primary_reason": primary_reason,
    }
    gate = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": evidence["status"],
        "decision": decision,
        "primary_reason": primary_reason,
        "deterministic_uplift_status": deterministic_uplift_status,
        "failure_transition_count": transition_count,
        "stage_2_unlock_count": stage_2_unlock_count,
        "stage_2_focus_count": stage_2_focus_count,
        "stage_plan_followed_count": stage_plan_followed_count,
        "stage_2_plan_followed_count": stage_2_plan_followed_count,
        "stage_2_resolution_count": stage_2_resolution_count,
        "local_search_success_count": local_search_success_count,
        "adaptive_search_success_count": adaptive_search_success_count,
        "stage_2_hard_case_resolution_count": stage_2_hard_case_resolution_count,
        "search_bad_direction_count": search_bad_direction_count,
        "stage_2_branch_count": stage_2_branch_count,
        "branch_selection_error_count": branch_selection_error_count,
        "good_branch_resolution_count": good_branch_resolution_count,
        "trap_branch_enter_count": trap_branch_enter_count,
        "trap_branch_recovery_count": trap_branch_recovery_count,
        "trap_branch_resolution_count": trap_branch_resolution_count,
        "preferred_branch_resolution_count": preferred_branch_resolution_count,
        "branch_escape_attempt_count": branch_escape_attempt_count,
        "branch_escape_success_count": branch_escape_success_count,
        "branch_budget_reallocated_count": branch_budget_reallocated_count,
        "repeated_trap_branch_count": repeated_trap_branch_count,
        "llm_request_count_total": llm_request_count_total,
        "llm_task_count": llm_task_count,
        "planner_backend_counts": planner_backend_counts,
        "resolved_llm_provider_counts": resolved_llm_provider_counts,
        "planner_family_counts": planner_family_counts,
        "planner_adapter_counts": planner_adapter_counts,
        "llm_plan_task_count": llm_plan_task_count,
        "llm_plan_followed_count": llm_plan_followed_count,
        "llm_plan_branch_match_count": llm_plan_branch_match_count,
        "first_plan_branch_match_count": first_plan_branch_match_count,
        "replan_branch_match_count": replan_branch_match_count,
        "llm_plan_helped_resolution_count": llm_plan_helped_resolution_count,
        "llm_plan_was_decisive_count": llm_plan_was_decisive_count,
        "llm_called_only_count": llm_called_only_count,
        "llm_replan_task_count": llm_replan_task_count,
        "llm_replan_used_count": llm_replan_used_count,
        "llm_replan_resolution_count": llm_replan_resolution_count,
        "llm_second_replan_used_count": llm_second_replan_used_count,
        "llm_second_replan_resolution_count": llm_second_replan_resolution_count,
        "first_plan_resolution_count": first_plan_resolution_count,
        "replan_after_branch_miss_count": replan_after_branch_miss_count,
        "backtracking_used_count": backtracking_used_count,
        "llm_guided_search_used_count": llm_guided_search_used_count,
        "search_budget_from_llm_plan_avg": search_budget_from_llm_plan_avg,
        "search_budget_followed_count": search_budget_followed_count,
        "llm_budget_helped_resolution_count": llm_budget_helped_resolution_count,
        "llm_guided_search_resolution_count": llm_guided_search_resolution_count,
        "llm_replan_budget_consumed_avg": llm_replan_budget_consumed_avg,
        "llm_replan_switch_branch_count": llm_replan_switch_branch_count,
        "llm_replan_same_branch_success_count": llm_replan_same_branch_success_count,
        "llm_replan_switch_branch_success_count": llm_replan_switch_branch_success_count,
        "llm_replan_budget_efficiency": llm_replan_budget_efficiency,
        "abandoned_branch_count": abandoned_branch_count,
        "budget_wasted_on_bad_branch_count": budget_wasted_on_bad_branch_count,
        "llm_resolution_count": llm_resolution_count,
        "llm_only_resolution_count": llm_only_resolution_count,
        "llm_branch_correction_count": llm_branch_correction_count,
        "trap_escape_success_count": trap_escape_success_count,
        "wrong_branch_enter_count": wrong_branch_enter_count,
        "wrong_branch_recovery_count": wrong_branch_recovery_count,
        "repeated_bad_branch_count": repeated_trap_branch_count,
        "stage_aware_control_status": stage_aware_control_status,
    }
    decision_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": evidence["status"],
        "decision": decision,
        "primary_reason": primary_reason,
        "all_scenarios_pass": evidence["all_scenarios_pass"],
        "partial_pass_pct": baseline_partial_pct,
        "failure_transition_count": transition_count,
        "stage_2_unlock_count": stage_2_unlock_count,
        "stage_2_unlock_pct": float(baseline_summary.get("stage_2_unlock_pct") or 0.0),
        "stage_2_focus_count": stage_2_focus_count,
        "stage_2_focus_pct": float(baseline_summary.get("stage_2_focus_pct") or 0.0),
        "stage_2_resolution_count": stage_2_resolution_count,
        "stage_2_resolution_pct": stage_2_resolution_pct,
        "stage_plan_followed_count": stage_plan_followed_count,
        "stage_plan_followed_pct": float(baseline_summary.get("stage_plan_followed_pct") or 0.0),
        "stage_2_plan_followed_count": stage_2_plan_followed_count,
        "stage_2_plan_followed_pct": float(baseline_summary.get("stage_2_plan_followed_pct") or 0.0),
        "stage_2_plan_resolution_count": stage_2_plan_resolution_count,
        "plan_conflict_rejected_count": plan_conflict_rejected_count,
        "local_search_attempt_count": local_search_attempt_count,
        "local_search_success_count": local_search_success_count,
        "local_search_success_pct": local_search_success_pct,
        "adaptive_search_attempt_count": adaptive_search_attempt_count,
        "adaptive_search_success_count": adaptive_search_success_count,
        "adaptive_search_success_pct": adaptive_search_success_pct,
        "stage_1_unlock_via_local_search_count": stage_1_unlock_via_local_search_count,
        "stage_2_resolution_via_local_search_count": stage_2_resolution_via_local_search_count,
        "cluster_only_resolution_count": cluster_only_resolution_count,
        "stage_1_unlock_via_adaptive_search_count": stage_1_unlock_via_adaptive_search_count,
        "stage_2_resolution_via_adaptive_search_count": stage_2_resolution_via_adaptive_search_count,
        "template_only_resolution_count": template_only_resolution_count,
        "adaptive_vs_template_resolution_split": adaptive_vs_template_resolution_split,
        "stage_2_hard_case_count": stage_2_hard_case_count,
        "stage_2_hard_case_resolution_count": stage_2_hard_case_resolution_count,
        "stage_2_hard_case_resolution_pct": stage_2_hard_case_resolution_pct,
        "search_bad_direction_count": search_bad_direction_count,
        "stage_2_branch_count": stage_2_branch_count,
        "stage_2_branch_pct": stage_2_branch_pct,
        "branch_selection_error_count": branch_selection_error_count,
        "good_branch_resolution_count": good_branch_resolution_count,
        "trap_branch_enter_count": trap_branch_enter_count,
        "trap_branch_recovery_count": trap_branch_recovery_count,
        "trap_escape_success_count": trap_escape_success_count,
        "trap_branch_resolution_count": trap_branch_resolution_count,
        "trap_branch_resolution_pct": trap_branch_resolution_pct,
        "preferred_branch_resolution_count": preferred_branch_resolution_count,
        "wrong_branch_enter_count": wrong_branch_enter_count,
        "wrong_branch_recovery_count": wrong_branch_recovery_count,
        "branch_escape_attempt_count": branch_escape_attempt_count,
        "branch_escape_success_count": branch_escape_success_count,
        "branch_escape_success_pct": branch_escape_success_pct,
        "branch_budget_reallocated_count": branch_budget_reallocated_count,
        "repeated_trap_branch_count": repeated_trap_branch_count,
        "repeated_bad_branch_count": repeated_trap_branch_count,
        "llm_request_count_total": llm_request_count_total,
        "llm_task_count": llm_task_count,
        "planner_backend_counts": planner_backend_counts,
        "resolved_llm_provider_counts": resolved_llm_provider_counts,
        "planner_family_counts": planner_family_counts,
        "planner_adapter_counts": planner_adapter_counts,
        "llm_plan_task_count": llm_plan_task_count,
        "llm_plan_followed_count": llm_plan_followed_count,
        "llm_plan_followed_pct": float(baseline_summary.get("llm_plan_followed_pct") or 0.0),
        "llm_plan_branch_match_count": llm_plan_branch_match_count,
        "llm_plan_branch_match_pct": float(baseline_summary.get("llm_plan_branch_match_pct") or 0.0),
        "first_plan_branch_match_count": first_plan_branch_match_count,
        "first_plan_branch_match_pct": float(baseline_summary.get("first_plan_branch_match_pct") or 0.0),
        "replan_branch_match_count": replan_branch_match_count,
        "replan_branch_match_pct": float(baseline_summary.get("replan_branch_match_pct") or 0.0),
        "llm_plan_helped_resolution_count": llm_plan_helped_resolution_count,
        "llm_plan_helped_resolution_pct": float(baseline_summary.get("llm_plan_helped_resolution_pct") or 0.0),
        "llm_plan_was_decisive_count": llm_plan_was_decisive_count,
        "llm_called_only_count": llm_called_only_count,
        "llm_replan_task_count": llm_replan_task_count,
        "llm_replan_used_count": llm_replan_used_count,
        "llm_replan_used_pct": float(baseline_summary.get("llm_replan_used_pct") or 0.0),
        "llm_replan_resolution_count": llm_replan_resolution_count,
        "llm_replan_resolution_pct": float(baseline_summary.get("llm_replan_resolution_pct") or 0.0),
        "llm_second_replan_used_count": llm_second_replan_used_count,
        "llm_second_replan_used_pct": float(baseline_summary.get("llm_second_replan_used_pct") or 0.0),
        "llm_second_replan_resolution_count": llm_second_replan_resolution_count,
        "llm_second_replan_resolution_pct": float(baseline_summary.get("llm_second_replan_resolution_pct") or 0.0),
        "first_plan_resolution_count": first_plan_resolution_count,
        "replan_after_branch_miss_count": replan_after_branch_miss_count,
        "backtracking_used_count": backtracking_used_count,
        "llm_guided_search_used_count": llm_guided_search_used_count,
        "llm_guided_search_used_pct": float(baseline_summary.get("llm_guided_search_used_pct") or 0.0),
        "search_budget_from_llm_plan_avg": search_budget_from_llm_plan_avg,
        "search_budget_followed_count": search_budget_followed_count,
        "search_budget_followed_pct": float(baseline_summary.get("search_budget_followed_pct") or 0.0),
        "llm_budget_helped_resolution_count": llm_budget_helped_resolution_count,
        "llm_budget_helped_resolution_pct": float(baseline_summary.get("llm_budget_helped_resolution_pct") or 0.0),
        "llm_guided_search_resolution_count": llm_guided_search_resolution_count,
        "llm_replan_budget_consumed_avg": llm_replan_budget_consumed_avg,
        "llm_replan_switch_branch_count": llm_replan_switch_branch_count,
        "llm_replan_same_branch_success_count": llm_replan_same_branch_success_count,
        "llm_replan_switch_branch_success_count": llm_replan_switch_branch_success_count,
        "llm_replan_budget_efficiency": llm_replan_budget_efficiency,
        "abandoned_branch_count": abandoned_branch_count,
        "budget_wasted_on_bad_branch_count": budget_wasted_on_bad_branch_count,
        "llm_resolution_count": llm_resolution_count,
        "llm_only_resolution_count": llm_only_resolution_count,
        "llm_branch_correction_count": llm_branch_correction_count,
        "llm_usage_by_failure_type": llm_usage_by_failure_type,
        "llm_usage_by_branch": llm_usage_by_branch,
        "deterministic_vs_llm_resolution_split": deterministic_vs_llm_resolution_split,
        "deterministic_vs_first_plan_vs_replan_split": deterministic_vs_first_plan_vs_replan_split,
        "median_round_to_correct_branch": median_round_to_correct_branch,
        "hard_case_remaining_buckets": hard_case_remaining_buckets,
        "stage_1_revisit_after_unlock_count": stage_1_revisit_after_unlock_count,
        "stage_aware_control_status": stage_aware_control_status,
        "deterministic_partial_to_full_count": partial_to_full_count,
        "deterministic_partial_to_full_pct": partial_to_full_pct,
        "deterministic_by_failure_type": partial_to_full_by_failure,
        "deterministic_uplift_status": deterministic_uplift_status,
    }
    _write_json(args.out, evidence)
    _write_json(args.gate_out, gate)
    _write_json(args.decision_out, decision_summary)
    print(json.dumps({"status": evidence["status"], "decision": decision, "primary_reason": primary_reason}))


if __name__ == "__main__":
    main()
