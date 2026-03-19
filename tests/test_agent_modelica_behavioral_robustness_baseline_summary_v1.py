import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaBehavioralRobustnessBaselineSummaryV1Tests(unittest.TestCase):
    def test_summary_reports_all_and_partial_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = {
                "total_tasks": 3,
                "taskset_frozen_path": str(root / "taskset.json"),
                "counts_by_failure_type": {
                    "param_perturbation_robustness_violation": 1,
                    "initial_condition_robustness_violation": 1,
                    "scenario_switch_robustness_violation": 1,
                },
                "counts_by_robustness_family": {
                    "param_perturbation": 1,
                    "initial_condition": 1,
                    "scenario_switch": 1,
                },
            }
            taskset = {
                "tasks": [
                    {"task_id": "t1", "failure_type": "param_perturbation_robustness_violation"},
                    {"task_id": "t2", "failure_type": "initial_condition_robustness_violation"},
                    {"task_id": "t3", "failure_type": "scenario_switch_robustness_violation"},
                ]
            }
            baseline_summary = {"status": "NEEDS_REVIEW", "success_count": 1, "success_at_k_pct": 33.33}
            baseline_results = {
                "records": [
                    {"task_id": "t1", "passed": False, "scenario_results": [{"pass": True}, {"pass": False}, {"pass": False}], "attempts": [{"round": 1}]},
                    {"task_id": "t2", "passed": False, "contract_fail_bucket": "initial_condition_miss", "scenario_results": [{"pass": False}, {"pass": False}, {"pass": False}], "attempts": [{"round": 1}, {"round": 2}]},
                    {"task_id": "t3", "passed": True, "scenario_results": [{"pass": True}, {"pass": True}, {"pass": True}], "attempts": [{"round": 1}]},
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
                    "gateforge.agent_modelica_behavioral_robustness_baseline_summary_v1",
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
            self.assertEqual(payload.get("scenario_fail_breakdown", {}).get("single_case_only"), 1)
            self.assertEqual(payload.get("scenario_fail_breakdown", {}).get("initial_condition_miss"), 1)
            self.assertEqual(payload.get("robustness_headroom_status"), "robustness_headroom_present")


if __name__ == "__main__":
    unittest.main()
