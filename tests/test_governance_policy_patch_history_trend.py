import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyPatchHistoryTrendTests(unittest.TestCase):
    def test_trend_with_previous_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps(
                    {
                        "total_records": 10,
                        "latest_status": "PASS",
                        "status_counts": {"PASS": 6, "NEEDS_REVIEW": 2, "FAIL": 2},
                        "applied_count": 6,
                        "reject_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "total_records": 5,
                        "latest_status": "FAIL",
                        "status_counts": {"PASS": 2, "NEEDS_REVIEW": 1, "FAIL": 2},
                        "applied_count": 2,
                        "reject_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_history_trend",
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
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("delta_total_records"), 5)
            self.assertAlmostEqual(trend.get("current_fail_rate"), 0.2)
            self.assertAlmostEqual(trend.get("previous_fail_rate"), 0.4)
            self.assertAlmostEqual(trend.get("delta_fail_rate"), -0.2)
            self.assertAlmostEqual(trend.get("current_apply_rate"), 0.6)
            self.assertAlmostEqual(trend.get("previous_apply_rate"), 0.4)
            self.assertAlmostEqual(trend.get("delta_apply_rate"), 0.2)

    def test_trend_without_previous_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps(
                    {
                        "total_records": 3,
                        "latest_status": "NEEDS_REVIEW",
                        "status_counts": {"PASS": 1, "NEEDS_REVIEW": 1, "FAIL": 1},
                        "applied_count": 1,
                        "reject_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_history_trend",
                    "--summary",
                    str(current),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("delta_total_records"), 3)
            self.assertEqual(trend.get("previous_fail_rate"), 0.0)
            self.assertEqual(trend.get("previous_apply_rate"), 0.0)
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
