import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetHistoryTrendTests(unittest.TestCase):
    def test_dataset_history_trend_needs_review_on_drops(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prev = root / "prev.json"
            cur = root / "cur.json"
            out = root / "trend.json"
            prev.write_text(
                json.dumps(
                    {
                        "total_records": 2,
                        "latest_deduplicated_cases": 12,
                        "latest_failure_case_rate": 0.35,
                        "freeze_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            cur.write_text(
                json.dumps(
                    {
                        "total_records": 3,
                        "latest_deduplicated_cases": 6,
                        "latest_failure_case_rate": 0.1,
                        "freeze_pass_rate": 0.6,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_history_trend",
                    "--summary",
                    str(cur),
                    "--previous-summary",
                    str(prev),
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
            alerts = payload.get("trend", {}).get("alerts", [])
            self.assertIn("deduplicated_case_count_drop_detected", alerts)
            self.assertIn("failure_case_rate_drop_detected", alerts)
            self.assertIn("freeze_pass_rate_drop_detected", alerts)

    def test_dataset_history_trend_pass_when_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prev = root / "prev.json"
            cur = root / "cur.json"
            out = root / "trend.json"
            prev.write_text(
                json.dumps(
                    {
                        "total_records": 1,
                        "latest_deduplicated_cases": 10,
                        "latest_failure_case_rate": 0.2,
                        "freeze_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            cur.write_text(
                json.dumps(
                    {
                        "total_records": 2,
                        "latest_deduplicated_cases": 11,
                        "latest_failure_case_rate": 0.22,
                        "freeze_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_history_trend",
                    "--summary",
                    str(cur),
                    "--previous-summary",
                    str(prev),
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
            self.assertEqual(payload.get("trend", {}).get("alerts", []), [])


if __name__ == "__main__":
    unittest.main()
