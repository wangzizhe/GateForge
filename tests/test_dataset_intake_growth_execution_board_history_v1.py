import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetIntakeGrowthExecutionBoardHistoryV1Tests(unittest.TestCase):
    def test_history_builds_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_score": 84.0,
                        "critical_open_tasks": 0,
                        "projected_weeks_to_target": 0,
                        "task_count": 1,
                        "alerts": [],
                    }
                ),
                encoding="utf-8",
            )
            r2.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "execution_score": 72.0,
                        "critical_open_tasks": 1,
                        "projected_weeks_to_target": 2,
                        "task_count": 3,
                        "alerts": ["critical_open_tasks_present"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_execution_board_history_v1",
                    "--record",
                    str(r1),
                    "--record",
                    str(r2),
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 2)
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})


if __name__ == "__main__":
    unittest.main()
