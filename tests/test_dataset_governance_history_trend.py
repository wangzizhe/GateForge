import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceHistoryTrendTests(unittest.TestCase):
    def test_trend_needs_review_on_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps(
                    {
                        "total_records": 10,
                        "status_counts": {"PASS": 4, "NEEDS_REVIEW": 2, "FAIL": 4},
                        "applied_count": 4,
                        "reject_count": 3,
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "total_records": 5,
                        "status_counts": {"PASS": 3, "NEEDS_REVIEW": 1, "FAIL": 1},
                        "applied_count": 3,
                        "reject_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_history_trend",
                    "--summary",
                    str(current),
                    "--previous-summary",
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
            alerts = payload.get("trend", {}).get("alerts", [])
            self.assertIn("dataset_governance_fail_rate_increasing", alerts)
            self.assertIn("dataset_governance_reject_rate_increasing", alerts)
            self.assertIn("dataset_governance_apply_rate_decreasing", alerts)

    def test_trend_pass_when_improving(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps(
                    {
                        "total_records": 10,
                        "status_counts": {"PASS": 8, "NEEDS_REVIEW": 1, "FAIL": 1},
                        "applied_count": 8,
                        "reject_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "total_records": 5,
                        "status_counts": {"PASS": 3, "NEEDS_REVIEW": 1, "FAIL": 1},
                        "applied_count": 3,
                        "reject_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_history_trend",
                    "--summary",
                    str(current),
                    "--previous-summary",
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
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("trend", {}).get("alerts", []), [])


if __name__ == "__main__":
    unittest.main()

