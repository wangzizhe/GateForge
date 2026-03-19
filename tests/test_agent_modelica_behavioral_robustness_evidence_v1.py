import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaBehavioralRobustnessEvidenceV1Tests(unittest.TestCase):
    def test_evidence_distinguishes_hold_the_floor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = {
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
                "scenario_count_distribution": {"3": 3},
            }
            taskset = {
                "tasks": [
                    {"task_id": "t1", "failure_type": "param_perturbation_robustness_violation", "robustness_family": "param_perturbation"},
                    {"task_id": "t2", "failure_type": "initial_condition_robustness_violation", "robustness_family": "initial_condition"},
                    {"task_id": "t3", "failure_type": "scenario_switch_robustness_violation", "robustness_family": "scenario_switch"},
                ]
            }
            baseline = {
                "all_scenarios_pass_pct": 33.33,
                "partial_pass_pct": 33.33,
                "scenario_fail_breakdown": {"single_case_only": 1, "initial_condition_miss": 1},
                "scenario_fail_by_failure_type": {
                    "param_perturbation_robustness_violation": {"task_count": 1, "scenario_fail_count": 1},
                    "initial_condition_robustness_violation": {"task_count": 1, "scenario_fail_count": 1},
                    "scenario_switch_robustness_violation": {"task_count": 1, "scenario_fail_count": 0},
                },
                "median_executor_attempts": 2.0,
            }
            deterministic_summary = {"all_scenarios_pass_pct": 100.0}
            retrieval_summary = {"all_scenarios_pass_pct": 100.0}
            baseline_results = {"records": [{"task_id": "t1", "contract_pass": False}, {"task_id": "t2", "contract_pass": False}, {"task_id": "t3", "contract_pass": True}]}
            deterministic_results = {"records": [{"task_id": "t1", "contract_pass": True, "attempts": [{"round": 1}]}, {"task_id": "t2", "contract_pass": True, "attempts": [{"round": 1}]}, {"task_id": "t3", "contract_pass": True, "attempts": [{"round": 1}]}]}
            retrieval_results = {"records": [{"task_id": "t1", "contract_pass": True, "attempts": [{"round": 1}]}, {"task_id": "t2", "contract_pass": True, "attempts": [{"round": 1}]}, {"task_id": "t3", "contract_pass": True, "attempts": [{"round": 1}]}]}
            for name, payload in {
                "challenge.json": challenge,
                "taskset.json": taskset,
                "baseline.json": baseline,
                "baseline_results.json": baseline_results,
                "det_summary.json": deterministic_summary,
                "det_results.json": deterministic_results,
                "ret_summary.json": retrieval_summary,
                "ret_results.json": retrieval_results,
            }.items():
                (root / name).write_text(json.dumps(payload), encoding="utf-8")
            out = root / "evidence.json"
            gate = root / "gate.json"
            decision = root / "decision.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_behavioral_robustness_evidence_v1",
                    "--challenge-summary",
                    str(root / "challenge.json"),
                    "--baseline-summary",
                    str(root / "baseline.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--deterministic-summary",
                    str(root / "det_summary.json"),
                    "--deterministic-results",
                    str(root / "det_results.json"),
                    "--retrieval-summary",
                    str(root / "ret_summary.json"),
                    "--retrieval-results",
                    str(root / "ret_results.json"),
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
            payload = json.loads(decision.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("deterministic_uplift_status"), "observed")
            self.assertEqual(payload.get("retrieval_uplift_status"), "retrieval_hold_the_floor")


if __name__ == "__main__":
    unittest.main()
