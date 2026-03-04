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


if __name__ == "__main__":
    unittest.main()

