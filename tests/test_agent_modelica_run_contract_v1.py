import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_run_contract_v1 import (
    _build_live_template_context,
    _classify_failure_domain_v1,
    _extract_contract_fields,
    _extract_live_usage_fields,
    _pick_manifestation_live_attempt,
)


class AgentModelicaRunContractV1Tests(unittest.TestCase):
    def test_classify_failure_domain_marks_source_block_incompatibility_as_environment(self) -> None:
        payload = _classify_failure_domain_v1(
            check_model_pass=False,
            simulate_pass=False,
            contract_pass=False,
            diagnostic_ir={"error_type": "model_check_error", "error_subtype": "compile_failure_unknown"},
            error_message="",
            compile_error="Class Modelica.Blocks.Sources.Trapezoid not found in scope HybridB.",
            simulate_error_message="",
            stderr_snippet="",
        )
        self.assertEqual(payload.get("failure_domain"), "environment")
        self.assertEqual(payload.get("environment_failure_kind"), "source_block_incompatible")
        self.assertEqual(payload.get("agent_failure_kind"), "")

    def test_classify_failure_domain_marks_wrong_branch_as_agent(self) -> None:
        payload = _classify_failure_domain_v1(
            check_model_pass=True,
            simulate_pass=True,
            contract_pass=False,
            diagnostic_ir={"error_type": "none", "error_subtype": "none"},
            error_message="",
            compile_error="",
            simulate_error_message="",
            stderr_snippet="",
            contract_fail_bucket="single_case_only",
            wrong_branch_entered=True,
            wrong_branch_recovered=False,
            trap_branch=True,
            branch_escape_attempted=True,
            branch_escape_succeeded=False,
        )
        self.assertEqual(payload.get("failure_domain"), "agent")
        self.assertEqual(payload.get("environment_failure_kind"), "")
        self.assertEqual(payload.get("agent_failure_kind"), "wrong_branch_enter")

    def test_extract_contract_fields_clears_fail_bucket_on_contract_pass(self) -> None:
        contract_pass, contract_fail_bucket, scenario_results, multistep = _extract_contract_fields(
            {
                "contract_pass": True,
                "contract_fail_bucket": "initial_condition_miss",
                "scenario_results": [
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            },
            {},
            physics_ok=True,
        )
        self.assertTrue(contract_pass)
        self.assertEqual(contract_fail_bucket, "")
        self.assertEqual([bool(x.get("pass")) for x in scenario_results], [True, True, True])
        self.assertFalse(bool(multistep.get("multi_step_stage_2_unlocked")))

    def test_extract_contract_fields_prefers_live_attempt_multistep_state(self) -> None:
        contract_pass, contract_fail_bucket, scenario_results, multistep = _extract_contract_fields(
            {
                "contract_pass": False,
                "contract_fail_bucket": "",
                "scenario_results": [],
                "multi_step_stage": "",
                "multi_step_stage_2_unlocked": False,
                "multi_step_transition_seen": False,
                "multi_step_transition_round": 0,
                "multi_step_transition_reason": "",
            },
            {
                "contract_pass": False,
                "contract_fail_bucket": "single_case_only",
                "scenario_results": [
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
                "multi_step_stage": "stage_2",
                "multi_step_stage_2_unlocked": True,
                "multi_step_transition_seen": True,
                "multi_step_transition_round": 2,
                "multi_step_transition_reason": "nominal_behavior_restored_neighbor_robustness_exposed",
                "current_stage": "stage_2",
                "stage_2_unlocked": True,
                "transition_round": 2,
                "transition_reason": "nominal_behavior_restored_neighbor_robustness_exposed",
                "current_fail_bucket": "single_case_only",
                "next_focus": "resolve_stage_2_neighbor_robustness",
                "stage_1_unlock_cluster": "switchb_unlock_cluster",
                "stage_2_first_fail_bucket": "single_case_only",
                "stage_2_branch": "nominal_overfit_trap",
                "preferred_stage_2_branch": "neighbor_robustness_branch",
                "branch_mode": "trap",
                "branch_reason": "nominal_gate_fully_reset_before_neighbor_robustness",
                "trap_branch": True,
                "trap_branch_entered": True,
                "wrong_branch_entered": True,
                "correct_branch_selected": False,
                "correct_branch_round": 0,
                "wrong_branch_recovered": False,
                "stage_aware_control_applied": True,
                "stage_1_revisit_after_unlock": False,
                "plan_stage": "stage_2",
                "plan_goal": "resolve the exposed second-stage neighbor robustness layer without reopening stage-1 nominal behavior",
                "plan_actions": ["resolve_stage_2_neighbor_robustness"],
                "plan_constraints": ["do_not_reopen_stage_1"],
                "plan_stop_condition": "all_neighbor_scenarios_pass",
                "branch_plan_goal": "escape the nominal_overfit_trap and return to neighbor_robustness_branch before resuming resolution",
                "branch_plan_actions": ["escape_trap_branch_nominal_overfit", "resolve_stage_2_neighbor_robustness"],
                "branch_plan_stop_condition": "preferred_branch_restored",
                "stage_plan_generated": True,
                "stage_plan_followed": True,
                "executed_plan_stage": "stage_2",
                "executed_plan_action": "resolve_stage_2_neighbor_robustness",
                "plan_followed": True,
                "plan_conflict_rejected": False,
                "plan_conflict_rejected_count": 0,
                "last_successful_stage_action": "unlock_stage_2_neighbor_robustness",
                "source_blind_multistep_local_search": {
                    "applied": True,
                    "search_kind": "stage_2_resolution",
                    "candidate_key": "stage_2_resolution:stage2_robustness_gain:k=0.5",
                },
                "tried_candidate_values": ["stage_1_unlock:stage1_nominal_start_freq:startTime=0.3|freqHz=1"],
                "bad_directions": ["width"],
                "successful_directions": ["k"],
                "local_search_attempt_count": 1,
                "local_search_success_count": 1,
                "local_search_kinds": ["stage_2_resolution"],
                "adaptive_search_attempt_count": 1,
                "adaptive_search_success_count": 1,
                "adaptive_search_success_pct": 100.0,
                "search_improvement_seen": True,
                "search_regression_seen": False,
                "search_bad_direction_count": 1,
                "best_stage_2_fail_bucket_seen": "single_case_only",
                "stage_2_best_progress_seen": True,
                "stage_1_unlock_via_local_search": False,
                "stage_2_resolution_via_local_search": True,
                "cluster_only_resolution": False,
                "stage_1_unlock_via_adaptive_search": False,
                "stage_2_resolution_via_adaptive_search": True,
                "template_only_resolution": False,
                "branch_history": ["neighbor_robustness_branch", "nominal_overfit_trap"],
                "trap_branch_history": ["nominal_overfit_trap"],
                "last_trap_escape_direction": "offset",
                "last_successful_branch_correction": "",
                "branch_bad_directions": ["nominal_gain_push"],
                "branch_reentry_count": 1,
                "repeated_trap_branch": True,
                "branch_escape_attempt_count": 1,
                "branch_escape_success_count": 0,
                "branch_escape_success_pct": 0.0,
                "branch_budget_reallocated_count": 1,
                "branch_escape_attempted": True,
                "branch_escape_succeeded": False,
                "branch_escape_direction": "offset",
                "branch_budget_reallocated": True,
                "realism_version": "v5",
                "planner_backend": "gemini",
                "resolved_llm_provider": "gemini",
                "planner_contract_version": "agent_modelica_multistep_planner_contract_v1",
                "planner_family": "llm",
                "planner_adapter": "gateforge_gemini_planner_v1",
                "planner_request_kind": "replan",
                "live_request_count": 2,
                "rate_limit_429_count": 0,
                "budget_stop_triggered": False,
                "llm_plan_used": True,
                "llm_plan_reason": "branch_diagnosis_unknown",
                "llm_plan_generated": True,
                "llm_plan_parsed": True,
                "llm_plan_followed": True,
                "llm_plan_branch_match": True,
                "first_plan_branch_match": False,
                "first_plan_branch_miss": True,
                "replan_branch_match": True,
                "replan_branch_corrected": True,
                "llm_plan_parameter_match": True,
                "llm_plan_helped_resolution": False,
                "llm_plan_was_decisive": False,
                "llm_called_only": False,
                "llm_plan_failure_mode": "",
                "llm_plan_diagnosed_stage": "stage_2",
                "llm_plan_diagnosed_branch": "nominal_overfit_trap",
                "llm_plan_preferred_branch": "neighbor_robustness_branch",
                "llm_plan_repair_goal": "escape trap and restore neighbor robustness",
                "llm_plan_candidate_parameters": ["offset", "k"],
                "llm_plan_candidate_value_directions": ["offset:normalize", "k:decrease"],
                "llm_plan_why_not_other_branch": "nominal-only branch overfits",
                "llm_plan_stop_condition": "stop when preferred branch is restored",
                "llm_request_count_delta": 1,
                "llm_branch_correction_used": True,
                "llm_resolution_contributed": False,
                "llm_only_resolution": False,
                "llm_replan_used": True,
                "llm_replan_reason": "same_stage_2_branch_stall_after_first_plan",
                "llm_replan_count": 1,
                "llm_second_replan_used": False,
                "llm_second_replan_reason": "",
                "previous_plan_failed_signal": "same_stage_2_branch_stall_after_first_plan",
                "previous_branch": "nominal_overfit_trap",
                "new_branch": "neighbor_robustness_branch",
                "replan_goal": "abandon nominal overfit and recover the preferred neighbor robustness branch",
                "replan_candidate_parameters": ["offset", "k"],
                "replan_stop_condition": "preferred_branch_restored",
                "branch_choice_reason": "switch to the preferred branch because the nominal branch stalled",
                "replan_budget_total": 3,
                "replan_budget_for_branch_diagnosis": 1,
                "replan_budget_for_branch_escape": 1,
                "replan_budget_for_resolution": 1,
                "replan_budget_consumed": 3,
                "replan_continue_current_branch": False,
                "replan_switch_branch": True,
                "replan_history": [{"round": 2, "signal": "same_stage_2_branch_stall_after_first_plan"}],
                "replan_branch_history": ["nominal_overfit_trap", "neighbor_robustness_branch"],
                "replan_failed_directions": ["offset:increase"],
                "replan_successful_directions": ["offset:normalize"],
                "replan_same_branch_stall_count": 1,
                "replan_switch_branch_count": 1,
                "replan_abandoned_branches": ["nominal_overfit_trap"],
                "backtracking_used": True,
                "backtracking_reason": "abandon_previous_branch_direction",
                "budget_reallocated_after_replan": True,
                "abandoned_plan_directions": ["offset:increase"],
                "replan_branch_correction_used": True,
                "replan_helped_resolution": False,
                "llm_first_plan_resolved": False,
                "llm_replan_resolved": False,
                "trap_escape_success": False,
                "llm_guided_search_used": True,
                "search_budget_from_llm_plan": 3,
                "search_budget_followed": True,
                "guided_search_bucket_sequence": ["branch_diagnosis", "branch_escape", "resolution"],
                "guided_search_order": "branch_diagnosis -> branch_escape -> resolution",
                "budget_bucket_consumed": {"branch_diagnosis": 1, "branch_escape": 1, "resolution": 1},
                "budget_bucket_exhausted": ["branch_diagnosis", "branch_escape", "resolution"],
                "candidate_suppressed_by_budget": 1,
                "candidate_attempt_count_by_bucket": {"branch_diagnosis": 1, "branch_escape": 1, "resolution": 1},
                "resolution_skipped_due_to_budget": False,
                "branch_escape_skipped_due_to_budget": False,
                "branch_frozen_by_budget": ["nominal_overfit_trap"],
                "guided_search_observation_payload": {"no_progress_buckets": ["branch_escape"]},
                "guided_search_replan_after_observation": True,
                "guided_search_closed_loop_observed": True,
                "guided_search_helped_branch_diagnosis": True,
                "guided_search_helped_trap_escape": True,
                "guided_search_helped_resolution": False,
                "guided_search_helped_replan": True,
                "guided_search_was_decisive": False,
                "llm_budget_helped_resolution": False,
                "llm_guided_search_resolution": False,
                "resolution_primary_contribution": "",
            },
            physics_ok=False,
        )
        self.assertFalse(contract_pass)
        self.assertEqual(contract_fail_bucket, "single_case_only")
        self.assertEqual(str(multistep.get("multi_step_stage") or ""), "stage_2")
        self.assertTrue(bool(multistep.get("multi_step_stage_2_unlocked")))
        self.assertEqual(int(multistep.get("multi_step_transition_round") or 0), 2)
        self.assertEqual(str(multistep.get("next_focus") or ""), "resolve_stage_2_neighbor_robustness")
        self.assertEqual(str(multistep.get("stage_2_branch") or ""), "nominal_overfit_trap")
        self.assertEqual(str(multistep.get("preferred_stage_2_branch") or ""), "neighbor_robustness_branch")
        self.assertEqual(str(multistep.get("branch_mode") or ""), "trap")
        self.assertTrue(bool(multistep.get("trap_branch")))
        self.assertTrue(bool(multistep.get("trap_branch_entered")))
        self.assertTrue(bool(multistep.get("wrong_branch_entered")))
        self.assertFalse(bool(multistep.get("correct_branch_selected")))
        self.assertFalse(bool(multistep.get("wrong_branch_recovered")))
        self.assertTrue(bool(multistep.get("stage_aware_control_applied")))
        self.assertEqual(str(multistep.get("plan_stage") or ""), "stage_2")
        self.assertTrue(bool(multistep.get("stage_plan_generated")))
        self.assertTrue(bool(multistep.get("stage_plan_followed")))
        self.assertEqual(str(multistep.get("executed_plan_action") or ""), "resolve_stage_2_neighbor_robustness")
        self.assertIn("escape", str(multistep.get("branch_plan_goal") or "").lower())
        self.assertEqual(multistep.get("branch_plan_actions"), ["escape_trap_branch_nominal_overfit", "resolve_stage_2_neighbor_robustness"])
        self.assertEqual(int(multistep.get("local_search_attempt_count") or 0), 1)
        self.assertTrue(bool(multistep.get("stage_2_resolution_via_local_search")))
        self.assertEqual(int(multistep.get("adaptive_search_attempt_count") or 0), 1)
        self.assertTrue(bool(multistep.get("stage_2_resolution_via_adaptive_search")))
        self.assertEqual(multistep.get("bad_directions"), ["width"])
        self.assertEqual(int(multistep.get("search_bad_direction_count") or 0), 1)
        self.assertEqual(str(multistep.get("best_stage_2_fail_bucket_seen") or ""), "single_case_only")
        self.assertTrue(bool(multistep.get("stage_2_best_progress_seen")))
        self.assertEqual(multistep.get("branch_history"), ["neighbor_robustness_branch", "nominal_overfit_trap"])
        self.assertEqual(multistep.get("trap_branch_history"), ["nominal_overfit_trap"])
        self.assertEqual(str(multistep.get("last_trap_escape_direction") or ""), "offset")
        self.assertEqual(multistep.get("branch_bad_directions"), ["nominal_gain_push"])
        self.assertEqual(int(multistep.get("branch_reentry_count") or 0), 1)
        self.assertTrue(bool(multistep.get("repeated_trap_branch")))
        self.assertEqual(int(multistep.get("branch_escape_attempt_count") or 0), 1)
        self.assertEqual(int(multistep.get("branch_escape_success_count") or 0), 0)
        self.assertTrue(bool(multistep.get("branch_escape_attempted")))
        self.assertFalse(bool(multistep.get("branch_escape_succeeded")))
        self.assertEqual(str(multistep.get("branch_escape_direction") or ""), "offset")
        self.assertTrue(bool(multistep.get("branch_budget_reallocated")))
        self.assertEqual(str(multistep.get("realism_version") or ""), "v5")
        self.assertEqual(str(multistep.get("branch_choice_reason") or ""), "switch to the preferred branch because the nominal branch stalled")
        self.assertEqual(int(multistep.get("replan_budget_total") or 0), 3)
        self.assertEqual(int(multistep.get("replan_budget_consumed") or 0), 3)
        self.assertTrue(bool(multistep.get("replan_switch_branch")))
        self.assertEqual(multistep.get("replan_abandoned_branches"), ["nominal_overfit_trap"])
        self.assertFalse(bool(multistep.get("first_plan_branch_match")))
        self.assertTrue(bool(multistep.get("first_plan_branch_miss")))
        self.assertTrue(bool(multistep.get("replan_branch_match")))
        self.assertTrue(bool(multistep.get("replan_branch_corrected")))
        self.assertFalse(bool(multistep.get("llm_second_replan_used")))
        self.assertTrue(bool(multistep.get("llm_guided_search_used")))
        self.assertEqual(int(multistep.get("search_budget_from_llm_plan") or 0), 3)
        self.assertTrue(bool(multistep.get("search_budget_followed")))
        self.assertEqual(multistep.get("guided_search_bucket_sequence"), ["branch_diagnosis", "branch_escape", "resolution"])
        self.assertEqual(str(multistep.get("guided_search_order") or ""), "branch_diagnosis -> branch_escape -> resolution")
        self.assertEqual(multistep.get("budget_bucket_exhausted"), ["branch_diagnosis", "branch_escape", "resolution"])
        self.assertEqual(int(multistep.get("candidate_suppressed_by_budget") or 0), 1)
        self.assertEqual(multistep.get("branch_frozen_by_budget"), ["nominal_overfit_trap"])
        self.assertTrue(bool(multistep.get("guided_search_replan_after_observation")))
        self.assertTrue(bool(multistep.get("guided_search_closed_loop_observed")))
        self.assertTrue(bool(multistep.get("guided_search_helped_branch_diagnosis")))
        self.assertTrue(bool(multistep.get("guided_search_helped_trap_escape")))
        self.assertFalse(bool(multistep.get("guided_search_helped_resolution")))
        self.assertTrue(bool(multistep.get("guided_search_helped_replan")))
        self.assertFalse(bool(multistep.get("guided_search_was_decisive")))
        self.assertEqual(str(multistep.get("resolution_primary_contribution") or ""), "")
        self.assertEqual((multistep.get("source_blind_multistep_local_search") or {}).get("search_kind"), "stage_2_resolution")

        live_usage = _extract_live_usage_fields(
            {
                "planner_backend": "gemini",
                "resolved_llm_provider": "gemini",
                "planner_contract_version": "agent_modelica_multistep_planner_contract_v1",
                "planner_family": "llm",
                "planner_adapter": "gateforge_gemini_planner_v1",
                "planner_request_kind": "replan",
                "live_request_count": 1,
            },
            {
                "realism_version": "v5",
                "first_plan_branch_match": False,
                "first_plan_branch_miss": True,
                "replan_branch_match": True,
                "replan_branch_corrected": True,
                "llm_replan_used": True,
                "llm_replan_reason": "same_stage_2_branch_stall_after_first_plan",
                "llm_replan_count": 1,
                "llm_second_replan_used": False,
                "llm_second_replan_reason": "",
                "previous_plan_failed_signal": "same_stage_2_branch_stall_after_first_plan",
                "previous_branch": "nominal_overfit_trap",
                "new_branch": "neighbor_robustness_branch",
                "branch_choice_reason": "switch to preferred branch",
                "replan_budget_total": 3,
                "replan_switch_branch": True,
                "backtracking_used": True,
                "budget_reallocated_after_replan": True,
                "abandoned_plan_directions": ["offset:increase"],
                "trap_escape_success": False,
                "llm_guided_search_used": True,
                "search_budget_from_llm_plan": 3,
                "search_budget_followed": True,
                "guided_search_bucket_sequence": ["branch_diagnosis", "branch_escape", "resolution"],
                "guided_search_order": "branch_diagnosis -> branch_escape -> resolution",
                "budget_bucket_consumed": {"branch_diagnosis": 1, "branch_escape": 1, "resolution": 1},
                "budget_bucket_exhausted": ["branch_diagnosis", "branch_escape", "resolution"],
                "candidate_suppressed_by_budget": 1,
                "candidate_attempt_count_by_bucket": {"branch_diagnosis": 1, "branch_escape": 1, "resolution": 1},
                "resolution_skipped_due_to_budget": False,
                "branch_escape_skipped_due_to_budget": False,
                "branch_frozen_by_budget": ["nominal_overfit_trap"],
                "guided_search_observation_payload": {"no_progress_buckets": ["branch_escape"]},
                "guided_search_replan_after_observation": True,
                "guided_search_closed_loop_observed": True,
                "guided_search_helped_branch_diagnosis": True,
                "guided_search_helped_trap_escape": True,
                "guided_search_helped_resolution": True,
                "guided_search_helped_replan": True,
                "guided_search_was_decisive": False,
                "llm_budget_helped_resolution": False,
                "llm_guided_search_resolution": True,
                "resolution_primary_contribution": "switch_branch_replan",
            },
        )
        self.assertEqual(str(live_usage.get("planner_contract_version") or ""), "agent_modelica_multistep_planner_contract_v1")
        self.assertEqual(str(live_usage.get("planner_family") or ""), "llm")
        self.assertEqual(str(live_usage.get("planner_adapter") or ""), "gateforge_gemini_planner_v1")
        self.assertEqual(str(live_usage.get("planner_request_kind") or ""), "replan")
        self.assertEqual(str(live_usage.get("realism_version") or ""), "v5")
        self.assertFalse(bool(live_usage.get("first_plan_branch_match")))
        self.assertTrue(bool(live_usage.get("first_plan_branch_miss")))
        self.assertTrue(bool(live_usage.get("replan_branch_match")))
        self.assertTrue(bool(live_usage.get("replan_branch_corrected")))
        self.assertTrue(bool(live_usage.get("llm_replan_used")))
        self.assertEqual(str(live_usage.get("llm_replan_reason") or ""), "same_stage_2_branch_stall_after_first_plan")
        self.assertEqual(int(live_usage.get("llm_replan_count") or 0), 1)
        self.assertFalse(bool(live_usage.get("llm_second_replan_used")))
        self.assertEqual(str(live_usage.get("previous_plan_failed_signal") or ""), "same_stage_2_branch_stall_after_first_plan")
        self.assertEqual(str(live_usage.get("previous_branch") or ""), "nominal_overfit_trap")
        self.assertEqual(str(live_usage.get("new_branch") or ""), "neighbor_robustness_branch")
        self.assertEqual(str(live_usage.get("branch_choice_reason") or ""), "switch to preferred branch")
        self.assertEqual(int(live_usage.get("replan_budget_total") or 0), 3)
        self.assertTrue(bool(live_usage.get("replan_switch_branch")))
        self.assertTrue(bool(live_usage.get("backtracking_used")))
        self.assertTrue(bool(live_usage.get("budget_reallocated_after_replan")))
        self.assertEqual(live_usage.get("abandoned_plan_directions"), ["offset:increase"])
        self.assertTrue(bool(live_usage.get("llm_guided_search_used")))
        self.assertEqual(int(live_usage.get("search_budget_from_llm_plan") or 0), 3)
        self.assertTrue(bool(live_usage.get("search_budget_followed")))
        self.assertEqual(live_usage.get("guided_search_bucket_sequence"), ["branch_diagnosis", "branch_escape", "resolution"])
        self.assertTrue(bool(live_usage.get("guided_search_closed_loop_observed")))
        self.assertTrue(bool(live_usage.get("guided_search_helped_branch_diagnosis")))
        self.assertTrue(bool(live_usage.get("guided_search_helped_trap_escape")))
        self.assertTrue(bool(live_usage.get("guided_search_helped_resolution")))
        self.assertTrue(bool(live_usage.get("guided_search_helped_replan")))
        self.assertFalse(bool(live_usage.get("guided_search_was_decisive")))
        self.assertTrue(bool(live_usage.get("llm_guided_search_resolution")))
        self.assertEqual(str(live_usage.get("resolution_primary_contribution") or ""), "switch_branch_replan")

    def test_extract_live_usage_fields_defaults_to_zero_visibility(self) -> None:
        fields = _extract_live_usage_fields({}, {})
        self.assertEqual(fields.get("realism_version"), "")
        self.assertFalse(bool(fields.get("first_plan_branch_match")))
        self.assertFalse(bool(fields.get("first_plan_branch_miss")))
        self.assertFalse(bool(fields.get("replan_branch_match")))
        self.assertFalse(bool(fields.get("replan_branch_corrected")))
        self.assertEqual(fields.get("planner_backend"), "")
        self.assertEqual(fields.get("resolved_llm_provider"), "")
        self.assertEqual(fields.get("planner_contract_version"), "")
        self.assertEqual(fields.get("planner_family"), "")
        self.assertEqual(fields.get("planner_adapter"), "")
        self.assertEqual(fields.get("planner_request_kind"), "")
        self.assertEqual(int(fields.get("live_request_count") or 0), 0)
        self.assertFalse(bool(fields.get("llm_guided_search_resolution")))
        self.assertFalse(bool(fields.get("guided_search_helped_branch_diagnosis")))
        self.assertFalse(bool(fields.get("guided_search_helped_trap_escape")))
        self.assertFalse(bool(fields.get("guided_search_helped_resolution")))
        self.assertFalse(bool(fields.get("guided_search_helped_replan")))
        self.assertFalse(bool(fields.get("guided_search_was_decisive")))
        self.assertEqual(str(fields.get("resolution_primary_contribution") or ""), "")
        self.assertEqual(int(fields.get("rate_limit_429_count") or 0), 0)
        self.assertFalse(bool(fields.get("budget_stop_triggered")))
        self.assertFalse(bool(fields.get("llm_plan_used")))
        self.assertEqual(int(fields.get("llm_request_count_delta") or 0), 0)
        self.assertFalse(bool(fields.get("llm_plan_generated")))
        self.assertFalse(bool(fields.get("llm_plan_parsed")))
        self.assertFalse(bool(fields.get("llm_plan_followed")))
        self.assertEqual(fields.get("llm_plan_candidate_parameters"), [])
        self.assertEqual(fields.get("llm_plan_candidate_value_directions"), [])
        self.assertFalse(bool(fields.get("llm_replan_used")))
        self.assertEqual(fields.get("llm_replan_reason"), "")
        self.assertEqual(int(fields.get("llm_replan_count") or 0), 0)
        self.assertFalse(bool(fields.get("llm_second_replan_used")))
        self.assertEqual(fields.get("llm_second_replan_reason"), "")
        self.assertEqual(fields.get("previous_plan_failed_signal"), "")
        self.assertEqual(fields.get("previous_branch"), "")
        self.assertEqual(fields.get("new_branch"), "")
        self.assertEqual(fields.get("branch_choice_reason"), "")
        self.assertEqual(int(fields.get("replan_budget_total") or 0), 0)
        self.assertFalse(bool(fields.get("replan_switch_branch")))
        self.assertFalse(bool(fields.get("backtracking_used")))
        self.assertFalse(bool(fields.get("budget_reallocated_after_replan")))
        self.assertEqual(fields.get("abandoned_plan_directions"), [])
        self.assertFalse(bool(fields.get("trap_escape_success")))
        self.assertFalse(bool(fields.get("llm_guided_search_used")))
        self.assertEqual(int(fields.get("search_budget_from_llm_plan") or 0), 0)
        self.assertFalse(bool(fields.get("search_budget_followed")))
        self.assertEqual(fields.get("guided_search_bucket_sequence"), [])
        self.assertFalse(bool(fields.get("guided_search_closed_loop_observed")))
        self.assertFalse(bool(fields.get("llm_budget_helped_resolution")))

    def test_extract_contract_fields_prefers_current_branch_state_over_payload_memory(self) -> None:
        _, _, _, multistep = _extract_contract_fields(
            {
                "contract_pass": False,
                "contract_fail_bucket": "single_case_only",
                "scenario_results": [
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
                "stage_2_branch": "post_switch_recovery_branch",
                "preferred_stage_2_branch": "post_switch_recovery_branch",
                "trap_branch": False,
                "correct_branch_selected": True,
                "correct_branch_round": 3,
            },
            {
                "contract_pass": False,
                "contract_fail_bucket": "single_case_only",
                "scenario_results": [
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
                "multi_step_stage": "stage_2",
                "multi_step_stage_2_unlocked": True,
                "stage_2_branch": "recovery_overfit_trap",
                "preferred_stage_2_branch": "post_switch_recovery_branch",
                "trap_branch": True,
                "trap_branch_entered": True,
                "wrong_branch_entered": True,
                "correct_branch_selected": False,
                "correct_branch_round": 0,
                "wrong_branch_recovered": False,
            },
            physics_ok=False,
        )
        self.assertEqual(str(multistep.get("stage_2_branch") or ""), "recovery_overfit_trap")
        self.assertTrue(bool(multistep.get("trap_branch")))
        self.assertTrue(bool(multistep.get("wrong_branch_entered")))
        self.assertFalse(bool(multistep.get("correct_branch_selected")))
        self.assertFalse(bool(multistep.get("wrong_branch_recovered")))

    def test_build_live_template_context_exposes_unknown_library_source_meta(self) -> None:
        context = _build_live_template_context(
            task={
                "task_id": "t1",
                "failure_type": "connector_mismatch",
                "expected_stage": "check",
                "source_model_path": "/tmp/source.mo",
                "mutated_model_path": "/tmp/mutated.mo",
                "source_meta": {
                    "package_name": "AixLib",
                    "library_id": "aixlib",
                    "local_path": "/repo/AixLib",
                    "model_path": "/repo/AixLib/Systems/Examples/Demo.mo",
                    "qualified_model_name": "AixLib.Systems.Examples.Demo",
                    "domain": "building_hvac",
                },
            },
            strategy={"actions": ["fix"]},
            round_idx=1,
            max_rounds=2,
            max_time_sec=180,
        )
        self.assertEqual(context["source_library_path"], "/repo/AixLib")
        self.assertEqual(context["source_package_name"], "AixLib")
        self.assertEqual(context["source_library_model_path"], "/repo/AixLib/Systems/Examples/Demo.mo")
        self.assertEqual(context["source_qualified_model_name"], "AixLib.Systems.Examples.Demo")
        self.assertEqual(context["source_domain"], "building_hvac")

    def test_pick_manifestation_live_attempt_prefers_multistep_unlock(self) -> None:
        attempt = _pick_manifestation_live_attempt(
            [
                {
                    "round": 1,
                    "observed_failure_type": "none",
                    "contract_fail_bucket": "behavior_contract_miss",
                    "scenario_results": [{"scenario_id": "nominal", "pass": False}],
                    "multi_step_stage": "stage_1",
                    "multi_step_stage_2_unlocked": False,
                    "multi_step_transition_seen": False,
                },
                {
                    "round": 2,
                    "observed_failure_type": "none",
                    "contract_fail_bucket": "single_case_only",
                    "scenario_results": [{"scenario_id": "nominal", "pass": True}, {"scenario_id": "neighbor_a", "pass": False}],
                    "multi_step_stage": "stage_2",
                    "multi_step_stage_2_unlocked": True,
                    "multi_step_transition_seen": True,
                },
            ],
            failure_type="behavior_then_robustness",
            expected_stage="simulate",
        )
        self.assertEqual(int(attempt.get("round") or 0), 2)

    def test_run_contract_mock_produces_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            experience_out = root / "experience.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "scale": "small", "failure_type": "model_check_error"},
                            {"task_id": "t2", "scale": "medium", "failure_type": "simulate_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--max-rounds",
                    "5",
                    "--max-time-sec",
                    "300",
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertIn(s.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(s.get("total_tasks", 0)), 2)
            self.assertEqual(len(r.get("records", [])), 2)
            self.assertIsNotNone(s.get("median_repair_rounds"))
            self.assertIn("repair_strategy", r["records"][0])
            self.assertTrue(str((r["records"][0].get("repair_strategy") or {}).get("strategy_id") or ""))

    def test_run_contract_applies_physics_contract_v0_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            experience_out = root / "experience.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_physics_fail",
                                "scale": "small",
                                "failure_type": "semantic_regression",
                                "mock_success_round": 1,
                                "mock_round_duration_sec": 5,
                                "baseline_metrics": {"steady_state_error": 0.01},
                                "candidate_metrics": {"steady_state_error": 0.2},
                                "physical_invariants": [
                                    {
                                        "type": "range",
                                        "metric": "steady_state_error",
                                        "min": 0.0,
                                        "max": 0.05,
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--max-rounds",
                    "3",
                    "--max-time-sec",
                    "60",
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(int(s.get("success_count", 0)), 0)
            self.assertEqual(int(s.get("physics_fail_count", 0)), 1)
            self.assertEqual(r.get("physics_contract_schema_version"), "physics_contract_v0")
            self.assertFalse(bool(r["records"][0]["hard_checks"]["physics_contract_pass"]))
            reasons = r["records"][0].get("physics_contract_reasons") or []
            self.assertTrue(any(str(x).startswith("physical_invariant_") for x in reasons))
            self.assertEqual((r["records"][0].get("repair_strategy") or {}).get("strategy_id"), "sem_invariant_first")

    def test_run_contract_evidence_mode_uses_real_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            results = root / "results.json"
            summary = root / "summary.json"
            baseline.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "gate": "PASS",
                        "check_ok": True,
                        "simulate_ok": True,
                        "metrics": {
                            "steady_state_error": 0.01,
                            "overshoot": 0.04,
                            "settling_time": 1.2,
                            "runtime_seconds": 2.0,
                            "events": 12,
                        },
                    }
                ),
                encoding="utf-8",
            )
            candidate.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "gate": "PASS",
                        "check_ok": True,
                        "simulate_ok": True,
                        "metrics": {
                            "steady_state_error": 0.02,
                            "overshoot": 0.05,
                            "settling_time": 1.5,
                            "runtime_seconds": 2.3,
                            "events": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_evidence",
                                "scale": "medium",
                                "failure_type": "semantic_regression",
                                "baseline_evidence_path": str(baseline),
                                "candidate_evidence_path": str(candidate),
                                "observed_repair_rounds": 2,
                                "observed_elapsed_sec": 40,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "evidence",
                    "--max-rounds",
                    "5",
                    "--max-time-sec",
                    "300",
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(s.get("mode"), "evidence")
            self.assertEqual(int(s.get("success_count", 0)), 1)
            self.assertEqual(int(s.get("physics_fail_count", 0)), 0)
            self.assertTrue(bool(r["records"][0]["hard_checks"]["regression_pass"]))
            self.assertEqual((r["records"][0].get("repair_strategy") or {}).get("strategy_id"), "sem_invariant_first")

    def test_run_contract_augments_strategy_with_templates_error_map_and_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            history = root / "history.json"
            results = root / "results.json"
            summary = root / "summary.json"
            history.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "failure_type": "model_check_error",
                                "model_id": "LargeGrid",
                                "used_strategy": "mc_undefined_symbol_guard",
                                "action_trace": ["declare missing symbol and align declaration scope"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_aug",
                                "scale": "large",
                                "failure_type": "model_check_error",
                                "source_model_path": "LargeGrid.mo",
                                "error_message": "Error: undefined symbol X",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--repair-history",
                    str(history),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            r = json.loads(results.read_text(encoding="utf-8"))
            rec = (r.get("records") or [])[0]
            audit = rec.get("repair_audit") or {}
            self.assertTrue(str(audit.get("patch_template_id") or "").startswith("tpl_"))
            self.assertTrue(str(audit.get("action_policy_channel") or ""))
            self.assertGreaterEqual(int(audit.get("error_action_count", 0)), 1)
            self.assertGreaterEqual(int(audit.get("retrieved_example_count", 0)), 1)
            self.assertIn("largegrid", audit.get("matched_component_hints", []))
            actions = audit.get("actions_planned") if isinstance(audit.get("actions_planned"), list) else []
            self.assertTrue(any("declare missing symbol" in str(x).lower() for x in actions))

    def test_run_contract_includes_retrieval_match_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            history = root / "history.json"
            results = root / "results.json"
            summary = root / "summary.json"
            history.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "failure_type": "connector_mismatch",
                                "model_id": "OpenIPSL.Tests.Solar.PSAT.SolarPVTest",
                                "used_strategy": "curated_openipsl_connector_mismatch",
                                "action_trace": ["align bus electrical connector semantics"],
                                "library_hints": ["openipsl"],
                                "component_hints": ["solarpvtest", "spv"],
                                "connector_hints": ["gen1.p", "spv.p", "p"],
                                "domains": ["power_system"],
                                "status": "PASS",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_unknown",
                                "scale": "small",
                                "failure_type": "connector_mismatch",
                                "expected_stage": "check",
                                "source_model_path": "OpenIPSL.Tests.Solar.PSAT.SolarPVTest.mo",
                                "library_hints": ["openipsl"],
                                "component_hints": ["SolarPVTest"],
                                "connector_hints": ["p"],
                                "domains": ["power_system"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--repair-history",
                    str(history),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            records = json.loads(results.read_text(encoding="utf-8")).get("records") or []
            audit = (records[0].get("repair_audit") or {}) if records else {}
            self.assertEqual(int(audit.get("library_match_count", 0)), 1)
            self.assertEqual(int(audit.get("component_match_count", 0)), 1)
            self.assertEqual(int(audit.get("domain_match_count", 0)), 1)
            self.assertIn("power_system", audit.get("matched_domain_hints", []))

    def test_run_contract_focus_queue_reduces_stress_runtime_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            focus_queue = root / "focus_queue.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_focus_reg",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "_stress_class": "slow_pass",
                                "_stress_reason": "slow_pass_runtime_stress",
                                "observed_repair_rounds": 2,
                                "observed_elapsed_sec": 80,
                                "baseline_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {
                                        "steady_state_error": 0.01,
                                        "overshoot": 0.04,
                                        "settling_time": 1.2,
                                        "runtime_seconds": 2.0,
                                        "events": 12,
                                    },
                                },
                                "candidate_evidence": {
                                    "status": "success",
                                    "gate": "PASS",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                    "metrics": {
                                        "steady_state_error": 0.01,
                                        "overshoot": 0.04,
                                        "settling_time": 1.2,
                                        "runtime_seconds": 3.0,
                                        "events": 12,
                                    },
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            focus_queue.write_text(
                json.dumps(
                    {
                        "queue": [
                            {
                                "rank": 1,
                                "failure_type": "simulate_error",
                                "gate_break_reason": "regression_fail",
                                "count": 5,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "evidence",
                    "--focus-queue",
                    str(focus_queue),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            r = json.loads(results.read_text(encoding="utf-8"))
            rec = (r.get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            self.assertTrue(bool((rec.get("hard_checks") or {}).get("regression_pass")))
            audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
            self.assertTrue(bool(audit.get("stress_repair_applied")))
            tags = audit.get("stress_repair_applied_tags") if isinstance(audit.get("stress_repair_applied_tags"), list) else []
            self.assertIn("repair_runtime_regression", tags)

    def test_run_contract_supports_learned_patch_and_retrieval_assets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            history = root / "history.json"
            patch_adapt = root / "patch_adapt.json"
            retrieval_policy = root / "retrieval_policy.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_learned",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "source_model_path": "LargeGrid.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "failure_type": "simulate_error",
                                "model_id": "LargeGrid",
                                "used_strategy": "sim_mem_boost",
                                "action_trace": ["memory-guided stabilize init"],
                                "status": "PASS",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            patch_adapt.write_text(
                json.dumps(
                    {
                        "failure_types": {
                            "simulate_error": {
                                "actions": ["memory-guided stabilize init"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            retrieval_policy.write_text(
                json.dumps(
                    {
                        "top_k_by_failure_type": {"simulate_error": 1},
                        "strategy_id_bonus_by_failure_type": {"simulate_error": {"sim_mem_boost": 1.0}},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--repair-history",
                    str(history),
                    "--patch-template-adaptations",
                    str(patch_adapt),
                    "--retrieval-policy",
                    str(retrieval_policy),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
            self.assertEqual(int(audit.get("patch_template_adaptation_actions_count", 0)), 1)
            self.assertEqual(int(audit.get("retrieval_effective_top_k", 0)), 1)

    def test_run_contract_adds_multi_round_family_specific_retrieval_guards(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            history = root / "history.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_multi_round_retrieval",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "multi_round_family": "coupled_conflict_failure",
                                "source_model_path": "ACSimpleGrid.mo",
                                "component_hints": ["ACSimpleGrid"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "failure_type": "simulate_error",
                                "model_id": "ACSimpleGrid",
                                "used_strategy": "paired_conflict_restore",
                                "action_trace": ["restore the conflicting paired binding before simulate"],
                                "status": "PASS",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--repair-history",
                    str(history),
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
            self.assertGreaterEqual(int(audit.get("retrieval_family_guard_count", 0)), 1)
            self.assertEqual(str(audit.get("retrieval_pairing_hint") or ""), "paired_conflict_repair_required")

    def test_run_contract_live_mode_executes_external_executor_command(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            experience_out = root / "experience.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": True, "
                "\"simulate_pass\": True, "
                "\"physics_contract_pass\": True, "
                "\"regression_pass\": True, "
                "\"elapsed_sec\": 5.5, "
                "\"error_message\": \"\", "
                "\"attempts\": [{"
                "\"observed_failure_type\": \"script_parse_error\", "
                "\"reason\": \"compile/syntax error\", "
                "\"log_excerpt\": \"No viable alternative\", "
                "\"pre_repair\": {\"applied\": True, \"reason\": \"removed_lines_with_injected_state_tokens\"}"
                "}]"
                "}))'"
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--experience-out",
                    str(experience_out),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(s.get("mode"), "live")
            self.assertEqual(int(s.get("success_count", 0)), 1)
            rec = (r.get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            self.assertTrue(bool((rec.get("hard_checks") or {}).get("regression_pass")))
            self.assertEqual(float(rec.get("elapsed_sec") or 0.0), 5.5)
            attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
            self.assertTrue(attempts)
            first_attempt = attempts[0] if isinstance(attempts[0], dict) else {}
            self.assertEqual(str(first_attempt.get("observed_failure_type") or ""), "script_parse_error")
            self.assertEqual(str(first_attempt.get("reason") or ""), "compile/syntax error")
            pre_repair = first_attempt.get("pre_repair") if isinstance(first_attempt.get("pre_repair"), dict) else {}
            self.assertTrue(bool(pre_repair.get("applied")))

    def test_run_contract_live_mode_supports_experience_replay_flags(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            experience_source = root / "memory.json"
            experience_source.write_text("{}", encoding="utf-8")
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_replay",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            code = """
import json
payload = {
  "check_model_pass": True,
  "simulate_pass": True,
  "physics_contract_pass": True,
  "regression_pass": True,
  "elapsed_sec": 1.0,
  "stderr_snippet": "__EXPERIENCE_REPLAY__|__EXPERIENCE_SOURCE__|__PLANNER_EXPERIENCE_INJECTION__|__PLANNER_EXPERIENCE_MAX_TOKENS__",
  "error_message": ""
}
print(json.dumps(payload))
""".strip()
            live_cmd = f"python3 -c {shlex.quote(code)}"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--experience-replay",
                    "on",
                    "--experience-source",
                    str(experience_source),
                    "--planner-experience-injection",
                    "on",
                    "--planner-experience-max-tokens",
                    "320",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(str(s.get("experience_replay") or ""), "on")
            self.assertEqual(str(r.get("experience_replay") or ""), "on")
            self.assertEqual(str(r.get("experience_source") or ""), str(experience_source))
            self.assertEqual(str(s.get("planner_experience_injection") or ""), "on")
            self.assertEqual(int(s.get("planner_experience_max_tokens") or 0), 320)
            self.assertEqual(str(r.get("planner_experience_injection") or ""), "on")
            self.assertEqual(int(r.get("planner_experience_max_tokens") or 0), 320)
            rec = (r.get("records") or [])[0]
            self.assertEqual(
                str(rec.get("stderr_snippet") or ""),
                f"on|{experience_source}|on|320",
            )

    def test_run_contract_live_mode_parses_multiline_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            experience_out = root / "experience.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_multiline",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": True, "
                "\"simulate_pass\": True, "
                "\"physics_contract_pass\": True, "
                "\"regression_pass\": True, "
                "\"elapsed_sec\": 1.2, "
                "\"attempts\": [{\"observed_failure_type\": \"script_parse_error\", \"reason\": \"compile/syntax error\"}]"
                "}, indent=2))'"
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--experience-out",
                    str(experience_out),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
            self.assertTrue(attempts)
            first_attempt = attempts[0] if isinstance(attempts[0], dict) else {}
            self.assertEqual(str(first_attempt.get("observed_failure_type") or ""), "script_parse_error")

    def test_run_contract_live_mode_preserves_contract_fields_on_top_level_record(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            experience_out = root / "experience.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_contract_fields",
                                "scale": "small",
                                "failure_type": "param_perturbation_robustness_violation",
                                "expected_stage": "simulate",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": True, "
                "\"simulate_pass\": True, "
                "\"physics_contract_pass\": False, "
                "\"contract_pass\": False, "
                "\"contract_fail_bucket\": \"param_sensitivity_miss\", "
                "\"scenario_results\": ["
                "{\"scenario_id\": \"nominal\", \"pass\": True}, "
                "{\"scenario_id\": \"neighbor_a\", \"pass\": False}, "
                "{\"scenario_id\": \"neighbor_b\", \"pass\": False}"
                "], "
                "\"regression_pass\": True, "
                "\"elapsed_sec\": 1.1, "
                "\"error_message\": \"param_sensitivity_miss\", "
                "\"attempts\": [{"
                "\"observed_failure_type\": \"none\", "
                "\"reason\": \"param_sensitivity_miss\", "
                "\"contract_pass\": False, "
                "\"contract_fail_bucket\": \"param_sensitivity_miss\", "
                "\"scenario_results\": ["
                "{\"scenario_id\": \"nominal\", \"pass\": True}, "
                "{\"scenario_id\": \"neighbor_a\", \"pass\": False}, "
                "{\"scenario_id\": \"neighbor_b\", \"pass\": False}"
                "]"
                "}]"
                "}))'"
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--max-rounds",
                    "1",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--experience-out",
                    str(experience_out),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertFalse(bool(rec.get("contract_pass")))
            self.assertEqual(str(rec.get("contract_fail_bucket") or ""), "param_sensitivity_miss")
            scenario_results = rec.get("scenario_results") if isinstance(rec.get("scenario_results"), list) else []
            self.assertEqual(len(scenario_results), 3)
            self.assertEqual([bool(x.get("pass")) for x in scenario_results], [True, False, False])
            attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
            self.assertTrue(attempts)
            self.assertEqual(str(attempts[0].get("contract_fail_bucket") or ""), "param_sensitivity_miss")

    def test_run_contract_live_mode_persists_manifestation_attempts_when_final_attempt_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_nested_manifestation",
                                "scale": "small",
                                "failure_type": "underconstrained_system",
                                "expected_stage": "check",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": True, "
                "\"simulate_pass\": True, "
                "\"physics_contract_pass\": True, "
                "\"regression_pass\": True, "
                "\"elapsed_sec\": 1.2, "
                "\"attempts\": ["
                "{"
                "\"observed_failure_type\": \"model_check_error\", "
                "\"reason\": \"structural underconstraint\", "
                "\"log_excerpt\": \"Class has 32 equation(s) and 33 variable(s).\", "
                "\"diagnostic_ir\": {"
                "\"error_type\": \"model_check_error\", "
                "\"error_subtype\": \"underconstrained_system\", "
                "\"stage\": \"check\", "
                "\"observed_phase\": \"simulate\""
                "}"
                "}, "
                "{"
                "\"observed_failure_type\": \"none\", "
                "\"reason\": \"\", "
                "\"log_excerpt\": \"\", "
                "\"diagnostic_ir\": {"
                "\"error_type\": \"none\", "
                "\"error_subtype\": \"none\", "
                "\"stage\": \"none\", "
                "\"observed_phase\": \"none\""
                "}"
                "}"
                "]"
                "}))'"
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
            self.assertTrue(attempts)
            first_attempt = attempts[0] if isinstance(attempts[0], dict) else {}
            self.assertEqual(str(first_attempt.get("observed_failure_type") or ""), "model_check_error")
            diagnostic = first_attempt.get("diagnostic_ir") if isinstance(first_attempt.get("diagnostic_ir"), dict) else {}
            self.assertEqual(str(diagnostic.get("error_subtype") or ""), "underconstrained_system")
            self.assertEqual(str(diagnostic.get("stage") or ""), "check")
            nested_attempts = first_attempt.get("attempts") if isinstance(first_attempt.get("attempts"), list) else []
            self.assertEqual(len(nested_attempts), 2)

    def test_run_contract_live_mode_auto_upgrades_legacy_repair_actions_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_legacy_placeholder",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": True, "
                "\"simulate_pass\": True, "
                "\"physics_contract_pass\": True, "
                "\"regression_pass\": True, "
                "\"elapsed_sec\": 1.0"
                "}))' "
                "--repair-actions \"__REPAIR_ACTIONS_JSON__\""
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
            self.assertIn(
                "upgrade_repair_actions_json_to_shq",
                [str(x) for x in (audit.get("live_command_normalizations") or [])],
            )

    def test_run_contract_live_mode_handles_escaped_quoted_repair_actions_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_escaped_placeholder",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": True, "
                "\"simulate_pass\": True, "
                "\"physics_contract_pass\": True, "
                "\"regression_pass\": True, "
                "\"elapsed_sec\": 1.0"
                "}))' "
                "--repair-actions \\\"__REPAIR_ACTIONS_JSON__\\\""
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
            normalizations = [str(x) for x in (audit.get("live_command_normalizations") or [])]
            self.assertIn("upgrade_repair_actions_json_to_shq", normalizations)
            self.assertIn("unquote_repair_actions_shq_escaped_double", normalizations)

    def test_run_contract_live_mode_labels_executor_invocation_error_when_command_parse_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_bash_parse_error",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "source_model_path": "assets_private/modelica/Minimal.mo",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = 'python3 -c "print("oops")'
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--max-rounds",
                    "1",
                    "--max-time-sec",
                    "30",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
            self.assertTrue(attempts)
            first_attempt = attempts[0] if isinstance(attempts[0], dict) else {}
            self.assertEqual(str(first_attempt.get("observed_failure_type") or ""), "executor_invocation_error")
            self.assertEqual(str(first_attempt.get("reason") or ""), "executor_invocation_error")

    def test_run_contract_live_mode_stops_on_no_progress_guard(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_no_progress",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            live_cmd = (
                "python3 -c 'import json; "
                "print(json.dumps({"
                "\"check_model_pass\": False, "
                "\"simulate_pass\": False, "
                "\"physics_contract_pass\": False, "
                "\"regression_pass\": False, "
                "\"elapsed_sec\": 0.2, "
                "\"observed_failure_type\": \"model_check_error\", "
                "\"error_message\": \"model check failed\", "
                "\"compile_error\": \"model check failed\""
                "}))'"
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--max-rounds",
                    "5",
                    "--max-time-sec",
                    "120",
                    "--live-timeout-sec",
                    "30",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertFalse(bool(rec.get("passed")))
            self.assertEqual(str(rec.get("error_message") or ""), "no_progress_stop")
            self.assertLessEqual(int(rec.get("rounds_used") or 0), 2)

    def test_run_contract_live_mode_preserves_best_contract_evidence_after_late_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            counter = root / "count.txt"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_best_contract_evidence",
                                "scale": "small",
                                "failure_type": "param_perturbation_robustness_violation",
                                "expected_stage": "simulate",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            code = """
import json
from pathlib import Path

counter = Path("__COUNTER__")
count = int(counter.read_text() or "0") if counter.exists() else 0
count += 1
counter.write_text(str(count))
if count == 1:
    payload = {
      "check_model_pass": True,
      "simulate_pass": True,
      "physics_contract_pass": False,
      "contract_pass": False,
      "contract_fail_bucket": "param_sensitivity_miss",
      "scenario_results": [
        {"scenario_id": "nominal", "pass": True},
        {"scenario_id": "neighbor_a", "pass": False},
        {"scenario_id": "neighbor_b", "pass": False},
      ],
      "regression_pass": True,
      "elapsed_sec": 1.0,
      "error_message": "param_sensitivity_miss"
    }
else:
    payload = {
      "_executor_return_code": None,
      "_executor_stdout_tail": "",
      "_executor_stderr_tail": "TimeoutExpired",
      "error_message": "live_executor_timeout",
      "elapsed_sec": 1.0
    }
print(json.dumps(payload))
""".strip().replace("__COUNTER__", str(counter))
            live_cmd = f"python3 -c {shlex.quote(code)}"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--max-rounds",
                    "3",
                    "--max-time-sec",
                    "30",
                    "--live-timeout-sec",
                    "5",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertFalse(bool(rec.get("passed")))
            self.assertEqual(str(rec.get("error_message") or ""), "no_progress_stop")
            self.assertFalse(bool(rec.get("contract_pass")))
            self.assertEqual(str(rec.get("contract_fail_bucket") or ""), "param_sensitivity_miss")
            scenario_results = rec.get("scenario_results") if isinstance(rec.get("scenario_results"), list) else []
            self.assertEqual([bool(x.get("pass")) for x in scenario_results], [True, False, False])

    def test_run_contract_live_mode_prefers_later_full_contract_pass_over_earlier_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            summary = root / "summary.json"
            counter = root / "count.txt"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_full_beats_partial",
                                "scale": "small",
                                "failure_type": "param_perturbation_robustness_violation",
                                "expected_stage": "simulate",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            code = """
import json
from pathlib import Path

counter = Path("__COUNTER__")
count = int(counter.read_text() or "0") if counter.exists() else 0
count += 1
counter.write_text(str(count))
if count == 1:
    payload = {
      "check_model_pass": True,
      "simulate_pass": True,
      "physics_contract_pass": False,
      "contract_pass": False,
      "contract_fail_bucket": "param_sensitivity_miss",
      "scenario_results": [
        {"scenario_id": "nominal", "pass": True},
        {"scenario_id": "neighbor_a", "pass": False},
        {"scenario_id": "neighbor_b", "pass": False}
      ],
      "regression_pass": True,
      "elapsed_sec": 1.0,
      "error_message": "param_sensitivity_miss"
    }
else:
    payload = {
      "check_model_pass": True,
      "simulate_pass": True,
      "physics_contract_pass": True,
      "contract_pass": True,
      "contract_fail_bucket": "",
      "scenario_results": [
        {"scenario_id": "nominal", "pass": True},
        {"scenario_id": "neighbor_a", "pass": True},
        {"scenario_id": "neighbor_b", "pass": True}
      ],
      "regression_pass": True,
      "elapsed_sec": 1.0,
      "error_message": ""
    }
print(json.dumps(payload))
""".strip().replace("__COUNTER__", str(counter))
            live_cmd = f"python3 -c {shlex.quote(code)}"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--max-rounds",
                    "3",
                    "--max-time-sec",
                    "30",
                    "--live-timeout-sec",
                    "5",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            rec = (json.loads(results.read_text(encoding="utf-8")).get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            self.assertTrue(bool(rec.get("contract_pass")))
            self.assertEqual(str(rec.get("contract_fail_bucket") or ""), "")
            scenario_results = rec.get("scenario_results") if isinstance(rec.get("scenario_results"), list) else []
            self.assertEqual([bool(x.get("pass")) for x in scenario_results], [True, True, True])

    def test_run_contract_live_mode_supports_l4_closed_loop_flags(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
            experience_out = root / "experience.json"
            summary = root / "summary.json"
            model_path = root / "A1.mo"
            model_path.write_text(
                "\n".join(
                    [
                        "model A1",
                        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                        "  Modelica.Electrical.Analog.Basic.Ground G1;",
                        "equation",
                        "  connect(R1.n, G1.p);",
                        "end A1;",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t_live_l4",
                                "scale": "small",
                                "failure_type": "model_check_error",
                                "expected_stage": "check",
                                "source_model_path": str(model_path),
                                "mutated_model_path": str(model_path),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            code = """
import json

is_l4 = "__L4_ENABLED__" == "1"
round_idx = int("__L4_ROUND__")
ok = bool(is_l4 and round_idx >= 2)
payload = {
  "check_model_pass": ok,
  "simulate_pass": ok,
  "physics_contract_pass": ok,
  "regression_pass": ok,
  "elapsed_sec": 0.2
}
if not ok:
  payload.update(
    {
      "error_message": "model check failed",
      "compile_error": "model check failed",
      "attempts": [
        {
          "observed_failure_type": "model_check_error",
          "reason": "compile/syntax error",
          "diagnostic_ir": {
            "error_type": "model_check_error",
            "error_subtype": "parse_lexer_error",
            "stage": "check",
            "confidence": 0.9
          }
        }
      ]
    }
  )
print(json.dumps(payload))
""".strip()
            live_cmd = f"python3 -c {shlex.quote(code)}"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--mode",
                    "live",
                    "--max-rounds",
                    "3",
                    "--max-time-sec",
                    "60",
                    "--live-timeout-sec",
                    "20",
                    "--l4-enabled",
                    "on",
                    "--l4-max-rounds",
                    "3",
                    "--l4-policy-backend",
                    "rule",
                    "--l4-policy-profile",
                    "score_v1",
                    "--l4-llm-fallback-threshold",
                    "2",
                    "--l4-max-actions-per-round",
                    "2",
                    "--live-executor-cmd",
                    live_cmd,
                    "--results-out",
                    str(results),
                    "--experience-out",
                    str(experience_out),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            s = json.loads(summary.read_text(encoding="utf-8"))
            r = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(s.get("mode"), "live")
            self.assertTrue(bool(s.get("l4_enabled")))
            self.assertEqual(str(s.get("l4_policy_profile") or ""), "score_v1")
            self.assertEqual(int(s.get("l4_llm_fallback_threshold") or 0), 2)
            self.assertGreaterEqual(int(s.get("experience_record_count") or 0), 1)
            self.assertEqual(str(s.get("experience_out") or ""), str(experience_out))
            self.assertIn("median_quality_score", s)
            self.assertIn("resolution_path_distribution", s)
            self.assertIn("dominant_stage_subtype_distribution", s)
            self.assertIn("planner_invoked_rate_pct", s)
            contrib = s.get("action_contribution_distribution") if isinstance(s.get("action_contribution_distribution"), dict) else {}
            self.assertIn("advancing", contrib)
            rec = (r.get("records") or [])[0]
            self.assertTrue(bool(rec.get("passed")))
            self.assertGreaterEqual(int(rec.get("rounds_used") or 0), 2)
            l4 = rec.get("l4") if isinstance(rec.get("l4"), dict) else {}
            self.assertTrue(bool(l4.get("enabled")))
            self.assertEqual(str(l4.get("policy_profile") or ""), "score_v1")
            self.assertIn(str(l4.get("l4_primary_reason") or ""), {"hard_checks_pass", "none"})
            self.assertIsInstance(l4.get("action_rank_trace"), list)
            self.assertIsInstance(l4.get("banned_action_signatures"), list)
            self.assertIn("llm_fallback_used", l4)
            self.assertGreaterEqual(len(l4.get("trajectory_rows") or []), 1)
            experience = r.get("experience_v1") if isinstance(r.get("experience_v1"), dict) else {}
            self.assertGreaterEqual(len(experience.get("records") or []), 1)
            exp_summary = experience.get("summary") if isinstance(experience.get("summary"), dict) else {}
            self.assertIn("median_quality_score", exp_summary)
            exp_record = (experience.get("records") or [])[0] if isinstance(experience.get("records"), list) else {}
            self.assertIn("repair_quality_score", exp_record)
            self.assertIsInstance(exp_record.get("action_contributions"), list)
            self.assertIn("resolution_path", exp_record)
            self.assertIn("dominant_stage_subtype", exp_record)
            exp_artifact = json.loads(experience_out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(exp_artifact.get("records") or []), 1)
            mem = r.get("repair_memory_v2") if isinstance(r.get("repair_memory_v2"), dict) else {}
            self.assertGreaterEqual(len(mem.get("trajectory_rows") or []), 1)

    def test_run_contract_resume_from_records_jsonl_skips_completed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            records_jsonl = root / "records.jsonl"
            results_a = root / "results_a.json"
            summary_a = root / "summary_a.json"
            results_b = root / "results_b.json"
            summary_b = root / "summary_b.json"

            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "scale": "small", "failure_type": "model_check_error"},
                            {"task_id": "t2", "scale": "small", "failure_type": "simulate_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc_a = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--records-jsonl",
                    str(records_jsonl),
                    "--results-out",
                    str(results_a),
                    "--out",
                    str(summary_a),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc_a.returncode, 0, msg=proc_a.stderr or proc_a.stdout)
            lines_a = [x for x in records_jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(lines_a), 2)

            proc_b = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_run_contract_v1",
                    "--taskset",
                    str(taskset),
                    "--records-jsonl",
                    str(records_jsonl),
                    "--resume-from-records",
                    "--results-out",
                    str(results_b),
                    "--out",
                    str(summary_b),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc_b.returncode, 0, msg=proc_b.stderr or proc_b.stdout)
            lines_b = [x for x in records_jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(lines_b), 2)

            summary = json.loads(summary_b.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("resumed_count", 0)), 2)


if __name__ == "__main__":
    unittest.main()
