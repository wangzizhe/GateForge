import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaAcceptanceGateV1Tests(unittest.TestCase):
    def test_acceptance_gate_marks_needs_review_on_soft_budget(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            out = root / "summary.json"
            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "rounds_used": 2,
                                "elapsed_sec": 100,
                                "hard_checks": {
                                    "check_model_pass": True,
                                    "simulate_pass": True,
                                    "physics_contract_pass": True,
                                    "regression_pass": True,
                                },
                            },
                            {
                                "task_id": "t2",
                                "scale": "medium",
                                "rounds_used": 6,
                                "elapsed_sec": 360,
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
                    "gateforge.agent_modelica_acceptance_gate_v1",
                    "--run-results",
                    str(run_results),
                    "--small-max-time-sec",
                    "300",
                    "--medium-max-time-sec",
                    "300",
                    "--small-max-rounds",
                    "5",
                    "--medium-max-rounds",
                    "5",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertEqual(int(payload.get("needs_review_count", 0)), 1)
            self.assertEqual(int(payload.get("fail_count", 0)), 0)


if __name__ == "__main__":
    unittest.main()

