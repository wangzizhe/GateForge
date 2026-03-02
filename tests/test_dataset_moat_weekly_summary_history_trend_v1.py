import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatWeeklySummaryHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"

            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "avg_real_model_count": 12.0,
                        "avg_stability_score": 90.0,
                        "avg_advantage_score": 10.0,
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "avg_real_model_count": 10.0,
                        "avg_stability_score": 85.0,
                        "avg_advantage_score": 8.0,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_weekly_summary_history_trend_v1",
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
            self.assertIn("avg_stability_score_decreasing", (payload.get("trend") or {}).get("alerts", []))


if __name__ == "__main__":
    unittest.main()
