import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetIntakeGrowthExecutionBoardHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_needs_review_on_worsen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "latest_board_status": "PASS",
                        "avg_execution_score": 82.0,
                        "critical_open_tasks_rate": 0.0,
                        "avg_projected_weeks_to_target": 0.2,
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_board_status": "NEEDS_REVIEW",
                        "avg_execution_score": 75.0,
                        "critical_open_tasks_rate": 0.5,
                        "avg_projected_weeks_to_target": 1.4,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_execution_board_history_trend_v1",
                    "--current",
                    str(current),
                    "--previous",
                    str(previous),
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


if __name__ == "__main__":
    unittest.main()
