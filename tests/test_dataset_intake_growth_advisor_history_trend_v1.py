import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetIntakeGrowthAdvisorHistoryTrendV1Tests(unittest.TestCase):
    def test_history_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(json.dumps({"status": "PASS", "latest_suggested_action": "keep", "recovery_plan_rate": 0.0, "targeted_patch_rate": 0.1, "avg_backlog_action_count": 0.5}), encoding="utf-8")
            current.write_text(json.dumps({"status": "NEEDS_REVIEW", "latest_suggested_action": "execute_growth_recovery_plan", "recovery_plan_rate": 0.4, "targeted_patch_rate": 0.2, "avg_backlog_action_count": 2.5}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_advisor_history_trend_v1",
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
            self.assertIn("recovery_plan_rate_increasing", (payload.get("trend") or {}).get("alerts", []))


if __name__ == "__main__":
    unittest.main()
