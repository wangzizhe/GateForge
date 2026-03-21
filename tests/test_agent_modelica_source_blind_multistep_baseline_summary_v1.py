import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaSourceBlindMultistepBaselineSummaryV1Tests(unittest.TestCase):
    def test_summary_reports_failure_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = {
                "total_tasks": 3,
                "taskset_frozen_path": str(root / "taskset.json"),
                "counts_by_failure_type": {
                    "stability_then_behavior": 1,
                    "behavior_then_robustness": 1,
                    "switch_then_recovery": 1,
                },
                "counts_by_multistep_family": {
                    "stability_then_behavior": 1,
                    "behavior_then_robustness": 1,
                    "switch_then_recovery": 1,
                },
            }
            taskset = {
                "tasks": [
                    {"task_id": "t1", "failure_type": "stability_then_behavior"},
                    {"task_id": "t2", "failure_type": "behavior_then_robustness"},
                    {"task_id": "t3", "failure_type": "switch_then_recovery"},
                ]
            }
            baseline_summary = {"status": "NEEDS_REVIEW", "success_count": 1, "success_at_k_pct": 33.33}
            baseline_results = {
                "records": [
                    {
                        "task_id": "t1",
                        "passed": True,
                        "multi_step_stage_2_unlocked": True,
                        "local_search_success_count": 1,
                        "adaptive_search_success_count": 1,
                        "search_bad_direction_count": 0,
                        "stage_1_unlock_via_local_search": True,
                        "stage_1_unlock_via_adaptive_search": True,
                        "stage_2_resolution_via_local_search": True,
                        "stage_2_resolution_via_adaptive_search": True,
                        "cluster_only_resolution": False,
                        "template_only_resolution": False,
                        "stage_2_first_fail_bucket": "behavior_contract_miss",
                        "scenario_results": [{"pass": True}, {"pass": True}, {"pass": True}],
                        "attempts": [
                            {"round": 1, "contract_fail_bucket": "stability_margin_miss", "multi_step_stage": "stage_1", "source_blind_multistep_local_search": {"applied": True, "search_kind": "stage_1_unlock", "candidate_key": "stage_1_unlock:stage1_stability_gain_height:k=1|height=1"}},
                            {"round": 2, "contract_fail_bucket": "behavior_contract_miss", "scenario_results": [{"pass": True}, {"pass": False}, {"pass": False}], "multi_step_stage": "stage_2", "multi_step_stage_2_unlocked": True, "multi_step_transition_seen": True, "multi_step_transition_round": 2, "multi_step_transition_reason": "stability_restored_behavior_gate_exposed", "source_blind_local_repair": {"applied": True, "cluster_name": "stability_cluster"}, "source_blind_multistep_local_search": {"applied": True, "search_kind": "stage_2_resolution", "candidate_key": "stage_2_resolution:stage2_behavior_start:startTime=0.2"}, "next_focus": "resolve_stage_2_behavior_contract", "stage_aware_control_applied": True, "stage_plan_generated": True, "stage_plan_followed": True, "plan_stage": "stage_2", "plan_followed": True, "executed_plan_action": "resolve_stage_2_behavior_contract"},
                            {"round": 3, "contract_pass": True, "scenario_results": [{"pass": True}, {"pass": True}, {"pass": True}], "multi_step_stage": "passed", "multi_step_stage_2_unlocked": True, "multi_step_transition_seen": True, "multi_step_transition_round": 2, "multi_step_transition_reason": "stability_restored_behavior_gate_exposed", "next_focus": "stop_editing", "stage_aware_control_applied": True, "stage_plan_generated": True, "stage_plan_followed": True, "plan_stage": "stage_2", "plan_followed": True, "executed_plan_action": "stop_editing"},
                        ],
                    },
                    {
                        "task_id": "t2",
                        "passed": False,
                        "multi_step_stage_2_unlocked": True,
                        "local_search_success_count": 0,
                        "adaptive_search_success_count": 0,
                        "search_bad_direction_count": 1,
                        "stage_1_unlock_via_local_search": True,
                        "stage_1_unlock_via_adaptive_search": True,
                        "stage_2_resolution_via_local_search": False,
                        "stage_2_resolution_via_adaptive_search": False,
                        "cluster_only_resolution": False,
                        "template_only_resolution": False,
                        "stage_2_first_fail_bucket": "single_case_only",
                        "scenario_results": [{"pass": True}, {"pass": False}, {"pass": False}],
                        "attempts": [
                            {"round": 1, "contract_fail_bucket": "behavior_contract_miss", "multi_step_stage": "stage_1", "source_blind_multistep_local_search": {"applied": True, "search_kind": "stage_1_unlock", "candidate_key": "stage_1_unlock:stage1_nominal_start_freq:startTime=0.3|freqHz=1"}},
                            {"round": 2, "contract_fail_bucket": "single_case_only", "scenario_results": [{"pass": True}, {"pass": False}, {"pass": False}], "multi_step_stage": "stage_2", "multi_step_stage_2_unlocked": True, "multi_step_transition_seen": True, "multi_step_transition_round": 2, "multi_step_transition_reason": "nominal_behavior_restored_neighbor_robustness_exposed", "next_focus": "resolve_stage_2_neighbor_robustness", "stage_aware_control_applied": True, "stage_plan_generated": True, "stage_plan_followed": True, "plan_stage": "stage_2", "plan_followed": True, "executed_plan_action": "resolve_stage_2_neighbor_robustness", "plan_conflict_rejected_count": 1},
                        ],
                    },
                    {
                        "task_id": "t3",
                        "passed": False,
                        "multi_step_stage_2_unlocked": False,
                        "local_search_success_count": 0,
                        "adaptive_search_success_count": 0,
                        "search_bad_direction_count": 0,
                        "stage_1_unlock_via_local_search": False,
                        "stage_1_unlock_via_adaptive_search": False,
                        "stage_2_resolution_via_local_search": False,
                        "stage_2_resolution_via_adaptive_search": False,
                        "cluster_only_resolution": True,
                        "template_only_resolution": True,
                        "contract_fail_bucket": "scenario_switch_miss",
                        "scenario_results": [{"pass": False}, {"pass": False}, {"pass": False}],
                        "attempts": [
                            {"round": 1, "contract_fail_bucket": "scenario_switch_miss", "multi_step_stage": "stage_1"},
                            {"round": 2, "contract_fail_bucket": "scenario_switch_miss", "multi_step_stage": "stage_1", "reason": "post_switch_recovery_miss"},
                        ],
                    },
                ]
            }
            (root / "challenge.json").write_text(json.dumps(challenge), encoding="utf-8")
            (root / "taskset.json").write_text(json.dumps(taskset), encoding="utf-8")
            (root / "baseline_summary.json").write_text(json.dumps(baseline_summary), encoding="utf-8")
            (root / "baseline_results.json").write_text(json.dumps(baseline_results), encoding="utf-8")
            out = root / "out.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_source_blind_multistep_baseline_summary_v1",
                    "--challenge-summary",
                    str(root / "challenge.json"),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("all_scenarios_pass_count"), 1)
            self.assertEqual(payload.get("partial_pass_count"), 1)
            self.assertEqual(payload.get("failure_transition_count"), 2)
            self.assertEqual(payload.get("stage_2_unlock_count"), 2)
            self.assertEqual(payload.get("stage_2_then_pass_count"), 1)
            self.assertEqual(payload.get("stage_2_then_fail_count"), 1)
            self.assertEqual(payload.get("stage_2_focus_count"), 2)
            self.assertEqual(payload.get("stage_1_revisit_after_unlock_count"), 0)
            self.assertEqual(payload.get("stage_2_resolution_count"), 1)
            self.assertEqual(payload.get("stage_2_resolution_pct"), 33.33)
            by_failure = payload.get("stage_2_resolution_by_failure_type") or {}
            self.assertEqual((by_failure.get("stability_then_behavior") or {}).get("stage_2_resolution_count"), 1)
            self.assertEqual(payload.get("stage_plan_generated_count"), 2)
            self.assertEqual(payload.get("stage_plan_followed_count"), 2)
            self.assertEqual(payload.get("stage_2_plan_generated_count"), 2)
            self.assertEqual(payload.get("stage_2_plan_followed_count"), 2)
            self.assertEqual(payload.get("stage_2_plan_resolution_count"), 1)
            self.assertEqual(payload.get("plan_conflict_rejected_count"), 1)
            self.assertEqual(payload.get("local_search_attempt_count"), 3)
            self.assertEqual(payload.get("local_search_success_count"), 1)
            self.assertEqual(payload.get("adaptive_search_success_count"), 1)
            self.assertEqual(payload.get("stage_1_unlock_via_local_search_count"), 2)
            self.assertEqual(payload.get("stage_2_resolution_via_local_search_count"), 1)
            self.assertEqual(payload.get("cluster_only_resolution_count"), 1)
            self.assertEqual(payload.get("stage_1_unlock_via_adaptive_search_count"), 2)
            self.assertEqual(payload.get("stage_2_resolution_via_adaptive_search_count"), 1)
            self.assertEqual(payload.get("template_only_resolution_count"), 1)
            self.assertEqual(payload.get("stage_2_hard_case_count"), 1)
            self.assertEqual(payload.get("stage_2_hard_case_resolution_count"), 1)
            self.assertEqual(payload.get("stage_2_hard_case_resolution_pct"), 100.0)
            self.assertEqual(payload.get("search_bad_direction_count"), 1)
            self.assertEqual(payload.get("hard_case_remaining_buckets"), {"single_case_only": 1})
            self.assertEqual(payload.get("adaptive_vs_template_resolution_split"), {"adaptive_search": 1, "template_only": 1})
            self.assertEqual(payload.get("multi_step_completion_count"), 1)
            self.assertEqual(payload.get("multi_step_headroom_status"), "stage_aware_control_observed")
            self.assertTrue(
                any("stability_cluster" in key for key in (payload.get("repair_action_sequence", {}) or {})),
                msg=str(payload.get("repair_action_sequence", {})),
            )
            self.assertTrue(
                any("resolve_stage_2" in key for key in (payload.get("stage_transition_action_sequence", {}) or {})),
                msg=str(payload.get("stage_transition_action_sequence", {})),
            )


if __name__ == "__main__":
    unittest.main()
