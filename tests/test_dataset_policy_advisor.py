import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyAdvisorTests(unittest.TestCase):
    def test_advisor_suggests_keep_when_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            history.write_text(
                json.dumps(
                    {
                        "latest_deduplicated_cases": 12,
                        "latest_failure_case_rate": 0.35,
                        "freeze_pass_rate": 1.0,
                        "alerts": [],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"status": "PASS", "trend": {"alerts": []}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_advisor",
                    "--dataset-history-summary",
                    str(history),
                    "--dataset-history-trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_action"), "keep")
            self.assertIn("dataset_signals_stable", advice.get("reasons", []))

    def test_advisor_suggests_hold_release_when_regressed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            history.write_text(
                json.dumps(
                    {
                        "latest_deduplicated_cases": 4,
                        "latest_failure_case_rate": 0.1,
                        "freeze_pass_rate": 0.6,
                        "alerts": ["latest_deduplicated_case_count_low"],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "trend": {"alerts": ["deduplicated_case_count_drop_detected", "failure_case_rate_drop_detected"]},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_advisor",
                    "--dataset-history-summary",
                    str(history),
                    "--dataset-history-trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_action"), "hold_release")
            reasons = advice.get("reasons", [])
            self.assertIn("dataset_case_count_below_policy", reasons)
            self.assertIn("dataset_history_trend_needs_review", reasons)
            self.assertIn("dataset_trend_alert_budget_exceeded", reasons)


if __name__ == "__main__":
    unittest.main()
