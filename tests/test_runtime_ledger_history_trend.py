import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RuntimeLedgerHistoryTrendTests(unittest.TestCase):
    def test_trend_detects_fail_and_review_growth(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps(
                    {
                        "total_records": 5,
                        "avg_pass_rate": 0.55,
                        "avg_fail_rate": 0.3,
                        "avg_needs_review_rate": 0.15,
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "total_records": 3,
                        "avg_pass_rate": 0.85,
                        "avg_fail_rate": 0.1,
                        "avg_needs_review_rate": 0.05,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.runtime_ledger_history_trend",
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
            alerts = (payload.get("trend") or {}).get("alerts", [])
            self.assertIn("avg_fail_rate_increasing", alerts)
            self.assertIn("avg_needs_review_rate_increasing", alerts)
            self.assertIn("avg_pass_rate_regression_detected", alerts)

    def test_trend_pass_without_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps(
                    {
                        "total_records": 6,
                        "avg_pass_rate": 0.8,
                        "avg_fail_rate": 0.1,
                        "avg_needs_review_rate": 0.1,
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "total_records": 5,
                        "avg_pass_rate": 0.78,
                        "avg_fail_rate": 0.11,
                        "avg_needs_review_rate": 0.11,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.runtime_ledger_history_trend",
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
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual((payload.get("trend") or {}).get("alerts", []), [])


if __name__ == "__main__":
    unittest.main()
