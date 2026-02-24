import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.runtime_ledger_trend import analyze_trend


class RuntimeLedgerTrendTests(unittest.TestCase):
    def test_analyze_trend_pass_without_alerts(self) -> None:
        current = {"total_records": 10, "kpis": {"pass_rate": 0.8, "fail_rate": 0.1, "needs_review_rate": 0.1}}
        previous = {"total_records": 8, "kpis": {"pass_rate": 0.78, "fail_rate": 0.11, "needs_review_rate": 0.11}}
        trend = analyze_trend(current, previous, fail_rate_alert_delta=0.05, needs_review_alert_delta=0.05)
        self.assertEqual(trend["status"], "PASS")
        self.assertEqual(trend["alerts"], [])

    def test_analyze_trend_needs_review_on_fail_rate_regression(self) -> None:
        current = {"total_records": 10, "kpis": {"pass_rate": 0.6, "fail_rate": 0.3, "needs_review_rate": 0.1}}
        previous = {"total_records": 8, "kpis": {"pass_rate": 0.8, "fail_rate": 0.1, "needs_review_rate": 0.1}}
        trend = analyze_trend(current, previous, fail_rate_alert_delta=0.05, needs_review_alert_delta=0.05)
        self.assertEqual(trend["status"], "NEEDS_REVIEW")
        self.assertIn("fail_rate_regression_detected", trend["alerts"])

    def test_cli_nonzero_when_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cur = root / "cur.json"
            prev = root / "prev.json"
            out = root / "trend.json"
            cur.write_text(
                json.dumps({"total_records": 10, "kpis": {"pass_rate": 0.6, "fail_rate": 0.3, "needs_review_rate": 0.1}}),
                encoding="utf-8",
            )
            prev.write_text(
                json.dumps({"total_records": 8, "kpis": {"pass_rate": 0.8, "fail_rate": 0.1, "needs_review_rate": 0.1}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.runtime_ledger_trend", "--current", str(cur), "--previous", str(prev), "--out", str(out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
