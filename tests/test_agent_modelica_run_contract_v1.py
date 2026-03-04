import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaRunContractV1Tests(unittest.TestCase):
    def test_run_contract_mock_produces_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            results = root / "results.json"
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

    def test_run_contract_applies_physics_contract_v0_invariants(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
