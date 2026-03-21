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
            self.assertEqual(payload.get("hard_case_remaining_buckets"), {"post_switch_recovery_miss": 1})


if __name__ == "__main__":
    unittest.main()
