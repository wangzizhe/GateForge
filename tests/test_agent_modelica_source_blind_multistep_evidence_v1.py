import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaSourceBlindMultistepEvidenceV1Tests(unittest.TestCase):
    def test_evidence_reports_partial_to_full_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = {
                "taskset_frozen_path": str(root / "taskset.json"),
                "total_tasks": 2,
            }
            taskset = {
                "tasks": [
                    {"task_id": "t1", "failure_type": "stability_then_behavior"},
                    {"task_id": "t2", "failure_type": "switch_then_recovery"},
                ]
            }
            baseline_summary = {
                "all_scenarios_pass_pct": 0.0,
                "partial_pass_pct": 100.0,
                "failure_transition_count": 1,
                "stage_2_unlock_count": 2,
                "stage_2_unlock_pct": 100.0,
                "median_round_to_stage_2": 2.0,
                "stage_2_then_fail_count": 2,
                "stage_2_then_pass_count": 0,
                "stage_2_focus_count": 2,
                "stage_2_focus_pct": 100.0,
                "stage_1_revisit_after_unlock_count": 0,
                "stage_2_resolution_count": 0,
                "stage_2_resolution_pct": 0.0,
                "stage_2_resolution_by_failure_type": {
                    "stability_then_behavior": {"task_count": 1, "stage_2_resolution_count": 0, "stage_2_resolution_pct": 0.0},
                    "switch_then_recovery": {"task_count": 1, "stage_2_resolution_count": 0, "stage_2_resolution_pct": 0.0},
                },
                "stage_plan_generated_count": 2,
                "stage_plan_generated_pct": 100.0,
                "stage_plan_followed_count": 2,
                "stage_plan_followed_pct": 100.0,
                "stage_2_plan_generated_count": 2,
                "stage_2_plan_generated_pct": 100.0,
                "stage_2_plan_followed_count": 2,
                "stage_2_plan_followed_pct": 100.0,
                "stage_2_plan_resolution_count": 0,
                "plan_conflict_rejected_count": 1,
                "local_search_attempt_count": 3,
                "local_search_success_count": 1,
                "local_search_success_pct": 50.0,
                "adaptive_search_attempt_count": 3,
                "adaptive_search_success_count": 1,
                "adaptive_search_success_pct": 50.0,
                "stage_1_unlock_via_local_search_count": 2,
                "stage_2_resolution_via_local_search_count": 1,
                "cluster_only_resolution_count": 0,
                "stage_1_unlock_via_adaptive_search_count": 2,
                "stage_2_resolution_via_adaptive_search_count": 1,
                "template_only_resolution_count": 0,
                "adaptive_vs_template_resolution_split": {"adaptive_search": 1, "template_only": 0},
                "stage_2_hard_case_count": 1,
                "stage_2_hard_case_resolution_count": 0,
                "stage_2_hard_case_resolution_pct": 0.0,
                "search_bad_direction_count": 1,
                "stage_2_branch_count": 2,
                "stage_2_branch_pct": 100.0,
                "branch_selection_error_count": 1,
                "good_branch_resolution_count": 0,
                "trap_branch_enter_count": 1,
                "trap_branch_recovery_count": 0,
                "trap_branch_resolution_count": 0,
                "trap_branch_resolution_pct": 0.0,
                "preferred_branch_resolution_count": 0,
                "branch_escape_attempt_count": 1,
                "branch_escape_success_count": 0,
                "branch_escape_success_pct": 0.0,
                "branch_budget_reallocated_count": 1,
                "repeated_trap_branch_count": 0,
                "llm_plan_task_count": 2,
                "llm_plan_followed_count": 2,
                "llm_plan_followed_pct": 100.0,
                "llm_plan_branch_match_count": 1,
                "llm_plan_branch_match_pct": 50.0,
                "first_plan_branch_match_count": 1,
                "first_plan_branch_match_pct": 50.0,
                "first_plan_branch_miss_count": 1,
                "first_plan_branch_miss_pct": 50.0,
                "replan_branch_match_count": 1,
                "replan_branch_match_pct": 50.0,
                "replan_branch_corrected_count": 1,
                "replan_branch_corrected_pct": 50.0,
                "llm_plan_helped_resolution_count": 1,
                "llm_plan_helped_resolution_pct": 50.0,
                "llm_plan_was_decisive_count": 0,
                "llm_called_only_count": 0,
                "llm_plan_failure_modes": {"same_stage_2_branch_stall_after_first_plan": 1},
                "llm_replan_task_count": 1,
                "llm_replan_used_count": 1,
                "llm_replan_used_pct": 50.0,
                "llm_replan_resolution_count": 1,
                "llm_replan_resolution_pct": 50.0,
                "llm_second_replan_used_count": 1,
                "llm_second_replan_used_pct": 50.0,
                "llm_second_replan_resolution_count": 1,
                "llm_second_replan_resolution_pct": 50.0,
                "first_plan_resolution_count": 0,
                "replan_after_branch_miss_count": 1,
                "backtracking_used_count": 1,
                "llm_guided_search_used_count": 2,
                "llm_guided_search_used_pct": 100.0,
                "search_budget_from_llm_plan_avg": 2.5,
                "search_budget_followed_count": 2,
                "search_budget_followed_pct": 100.0,
                "guided_search_closed_loop_count": 1,
                "guided_search_closed_loop_pct": 50.0,
                "guided_search_replan_after_observation_count": 1,
                "guided_search_helped_branch_diagnosis_count": 2,
                "guided_search_helped_trap_escape_count": 1,
                "guided_search_helped_resolution_count": 2,
                "guided_search_helped_replan_count": 1,
                "guided_search_was_decisive_count": 0,
                "budget_bucket_exhausted_count": 1,
                "resolution_skipped_due_to_budget_count": 0,
                "candidate_suppressed_by_budget_count": 1,
                "llm_budget_helped_resolution_count": 2,
                "llm_budget_helped_resolution_pct": 100.0,
                "llm_guided_search_resolution_count": 2,
                "llm_replan_budget_consumed_avg": 3.0,
                "llm_replan_switch_branch_count": 1,
                "llm_replan_same_branch_success_count": 0,
                "llm_replan_switch_branch_success_count": 1,
                "llm_replan_budget_efficiency": 33.33,
                "abandoned_branch_count": 1,
                "budget_wasted_on_bad_branch_count": 1,
                "llm_request_count_total": 2,
                "llm_task_count": 2,
                "planner_backend_counts": {"gemini": 2},
                "resolved_llm_provider_counts": {"gemini": 2},
                "planner_family_counts": {"llm": 2},
                "planner_adapter_counts": {"gateforge_gemini_planner_v1": 2},
                "failure_domain_counts": {"none": 0, "environment": 1, "agent": 1, "mixed": 0, "unknown": 0},
                "environment_failure_count": 1,
                "agent_failure_count": 1,
                "mixed_failure_count": 0,
                "unknown_failure_count": 0,
                "environment_failure_by_kind": {"source_block_incompatible": 1},
                "agent_failure_by_kind": {"wrong_branch_enter": 1},
                "llm_resolution_count": 1,
                "llm_only_resolution_count": 0,
                "llm_branch_correction_count": 1,
                "deterministic_resolution_count": 0,
                "llm_first_plan_resolution_count": 1,
                "switch_branch_replan_resolution_count": 1,
                "guided_search_assisted_resolution_count": 0,
                "guided_search_decisive_resolution_count": 0,
                "trap_escape_success_count": 1,
                "wrong_branch_enter_count": 1,
                "wrong_branch_recovery_count": 0,
                "llm_usage_by_failure_type": {"stability_then_behavior": 1, "switch_then_recovery": 1},
                "llm_usage_by_branch": {"behavior_timing_branch": 1},
                "deterministic_vs_llm_resolution_split": {"adaptive_search": 1, "template_only": 0, "llm_contributed": 1, "llm_only": 0},
                "deterministic_vs_first_plan_vs_replan_split": {"deterministic": 0, "llm_first_plan": 0, "llm_replan": 1, "llm_second_replan": 1},
                "resolution_attribution_split": {"deterministic": 0, "llm_first_plan": 1, "llm_replan": 0, "switch_branch_replan": 1, "guided_search_assisted": 0, "guided_search_decisive": 0},
                "resolution_primary_contribution_counts": {"llm_first_plan": 1, "switch_branch_replan": 1},
                "median_round_to_correct_branch": 2.0,
                "hard_case_remaining_buckets": {"post_switch_recovery_miss": 1},
                "median_round_from_stage_2_to_resolution": 0.0,
                "multi_step_completion_count": 0,
                "median_round_to_second_failure": 2.0,
                "repair_action_sequence": {"a -> b": 1},
                "stage_transition_action_sequence": {"resolve_stage_2_behavior_contract -> stop_editing": 1},
            }
            baseline_results = {
                "records": [
                    {"task_id": "t1", "scenario_results": [{"pass": True}, {"pass": False}, {"pass": False}]},
                    {"task_id": "t2", "scenario_results": [{"pass": True}, {"pass": False}, {"pass": False}]},
                ]
            }
            deterministic_summary = {"all_scenarios_pass_pct": 100.0}
            deterministic_results = {
                "records": [
                    {"task_id": "t1", "scenario_results": [{"pass": True}, {"pass": True}, {"pass": True}]},
                    {"task_id": "t2", "scenario_results": [{"pass": True}, {"pass": True}, {"pass": True}]},
                ]
            }
            for name, payload in (
                ("challenge.json", challenge),
                ("taskset.json", taskset),
                ("baseline_summary.json", baseline_summary),
                ("baseline_results.json", baseline_results),
                ("deterministic_summary.json", deterministic_summary),
                ("deterministic_results.json", deterministic_results),
            ):
                (root / name).write_text(json.dumps(payload), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_source_blind_multistep_evidence_v1",
                    "--challenge-summary",
                    str(root / "challenge.json"),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--deterministic-summary",
                    str(root / "deterministic_summary.json"),
                    "--deterministic-results",
                    str(root / "deterministic_results.json"),
                    "--out",
                    str(out),
                    "--gate-out",
                    str(gate),
                    "--decision-out",
                    str(decision),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("deterministic_partial_to_full_count"), 2)
            self.assertEqual(payload.get("deterministic_uplift_status"), "observed")
            self.assertEqual(payload.get("stage_aware_control_status"), "stage_aware_control_observed")
            self.assertEqual(payload.get("stage_2_resolution_pct"), 0.0)
            self.assertEqual(payload.get("stage_plan_followed_count"), 2)
            self.assertEqual(payload.get("stage_2_plan_followed_count"), 2)
            self.assertEqual(payload.get("plan_conflict_rejected_count"), 1)
            self.assertEqual(payload.get("local_search_attempt_count"), 3)
            self.assertEqual(payload.get("local_search_success_count"), 1)
            self.assertEqual(payload.get("stage_2_resolution_via_local_search_count"), 1)
            self.assertEqual(payload.get("adaptive_search_attempt_count"), 3)
            self.assertEqual(payload.get("adaptive_search_success_count"), 1)
            self.assertEqual(payload.get("stage_2_resolution_via_adaptive_search_count"), 1)
            self.assertEqual(payload.get("stage_2_hard_case_count"), 1)
            self.assertEqual(payload.get("search_bad_direction_count"), 1)
            self.assertEqual(payload.get("stage_2_branch_count"), 2)
            self.assertEqual(payload.get("branch_selection_error_count"), 1)
            self.assertEqual(payload.get("trap_branch_enter_count"), 1)
            self.assertEqual(payload.get("llm_request_count_total"), 2)
            self.assertEqual(payload.get("llm_task_count"), 2)
            self.assertEqual(payload.get("planner_backend_counts"), {"gemini": 2})
            self.assertEqual(payload.get("resolved_llm_provider_counts"), {"gemini": 2})
            self.assertEqual(payload.get("planner_family_counts"), {"llm": 2})
            self.assertEqual(payload.get("planner_adapter_counts"), {"gateforge_gemini_planner_v1": 2})
            self.assertEqual(payload.get("failure_domain_counts"), {"none": 0, "environment": 1, "agent": 1, "mixed": 0, "unknown": 0})
            self.assertEqual(payload.get("environment_failure_count"), 1)
            self.assertEqual(payload.get("agent_failure_count"), 1)
            self.assertEqual(payload.get("environment_failure_by_kind"), {"source_block_incompatible": 1})
            self.assertEqual(payload.get("agent_failure_by_kind"), {"wrong_branch_enter": 1})
            self.assertEqual(payload.get("llm_plan_task_count"), 2)
            self.assertEqual(payload.get("llm_plan_followed_count"), 2)
            self.assertEqual(payload.get("first_plan_branch_match_count"), 1)
            self.assertEqual(payload.get("first_plan_branch_miss_count"), 1)
            self.assertEqual(payload.get("replan_branch_match_count"), 1)
            self.assertEqual(payload.get("replan_branch_corrected_count"), 1)
            self.assertEqual(payload.get("llm_resolution_count"), 1)
            self.assertEqual(payload.get("llm_branch_correction_count"), 1)
            self.assertEqual(payload.get("llm_replan_task_count"), 1)
            self.assertEqual(payload.get("llm_replan_used_count"), 1)
            self.assertEqual(payload.get("llm_replan_resolution_count"), 1)
            self.assertEqual(payload.get("llm_second_replan_used_count"), 1)
            self.assertEqual(payload.get("llm_second_replan_resolution_count"), 1)
            self.assertEqual(payload.get("first_plan_resolution_count"), 0)
            self.assertEqual(payload.get("replan_after_branch_miss_count"), 1)
            self.assertEqual(payload.get("backtracking_used_count"), 1)
            self.assertEqual(payload.get("llm_guided_search_used_count"), 2)
            self.assertEqual(payload.get("search_budget_from_llm_plan_avg"), 2.5)
            self.assertEqual(payload.get("search_budget_followed_count"), 2)
            self.assertEqual(payload.get("guided_search_closed_loop_count"), 1)
            self.assertEqual(payload.get("guided_search_replan_after_observation_count"), 1)
            self.assertEqual(payload.get("guided_search_helped_branch_diagnosis_count"), 2)
            self.assertEqual(payload.get("guided_search_helped_trap_escape_count"), 1)
            self.assertEqual(payload.get("guided_search_helped_resolution_count"), 2)
            self.assertEqual(payload.get("guided_search_helped_replan_count"), 1)
            self.assertEqual(payload.get("guided_search_was_decisive_count"), 0)
            self.assertEqual(payload.get("budget_bucket_exhausted_count"), 1)
            self.assertEqual(payload.get("candidate_suppressed_by_budget_count"), 1)
            self.assertEqual(payload.get("llm_budget_helped_resolution_count"), 2)
            self.assertEqual(payload.get("llm_guided_search_resolution_count"), 2)
            self.assertEqual(payload.get("llm_replan_budget_consumed_avg"), 3.0)
            self.assertEqual(payload.get("llm_replan_switch_branch_count"), 1)
            self.assertEqual(payload.get("llm_replan_budget_efficiency"), 33.33)
            self.assertEqual(payload.get("abandoned_branch_count"), 1)
            self.assertEqual(payload.get("trap_escape_success_count"), 1)
            self.assertEqual(payload.get("wrong_branch_enter_count"), 1)
            self.assertEqual(payload.get("wrong_branch_recovery_count"), 0)
            self.assertEqual(payload.get("repeated_bad_branch_count"), 0)
            self.assertEqual(payload.get("deterministic_vs_llm_resolution_split"), {"adaptive_search": 1, "template_only": 0, "llm_contributed": 1, "llm_only": 0})
            self.assertEqual(payload.get("deterministic_vs_first_plan_vs_replan_split"), {"deterministic": 0, "llm_first_plan": 0, "llm_replan": 1, "llm_second_replan": 1})
            self.assertEqual(payload.get("resolution_attribution_split"), {"deterministic": 0, "llm_first_plan": 1, "llm_replan": 0, "switch_branch_replan": 1, "guided_search_assisted": 0, "guided_search_decisive": 0})
            self.assertEqual(payload.get("median_round_to_correct_branch"), 2.0)
            self.assertEqual(payload.get("hard_case_remaining_buckets"), {"post_switch_recovery_miss": 1})


if __name__ == "__main__":
    unittest.main()
