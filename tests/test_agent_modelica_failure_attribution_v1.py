import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaFailureAttributionV1Tests(unittest.TestCase):
    def test_extracts_failed_rows_with_reason_and_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            out = root / "attr.json"
            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "simulate_error",
                                "passed": False,
                                "hard_checks": {
                                    "check_model_pass": True,
                                    "simulate_pass": False,
                                    "physics_contract_pass": False,
                                    "regression_pass": True,
                                },
                                "repair_audit": {"strategy_id": "sim_x", "actions_planned": ["a1", "a2"]},
                            },
                            {
                                "task_id": "t2",
                                "scale": "medium",
                                "failure_type": "model_check_error",
                                "passed": True,
                                "hard_checks": {
                                    "check_model_pass": True,
                                    "simulate_pass": True,
                                    "physics_contract_pass": True,
                                    "regression_pass": True,
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_failure_attribution_v1",
                    "--run-results",
                    str(run_results),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("failed_count", 0)), 1)
            row = (payload.get("rows") or [])[0]
            self.assertEqual(row.get("task_id"), "t1")
            self.assertEqual(row.get("gate_break_reason"), "simulate_fail")
            self.assertEqual(row.get("used_strategy"), "sim_x")


if __name__ == "__main__":
    unittest.main()
