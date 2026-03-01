import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAnchorModelPackHistoryTrendV1Tests(unittest.TestCase):
    def test_history_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps({"status": "PASS", "avg_pack_quality_score": 84.0, "avg_selected_cases": 24.0, "avg_selected_large_cases": 8.0, "avg_unique_failure_types": 6.0}),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "avg_pack_quality_score": 80.0, "avg_selected_cases": 23.0, "avg_selected_large_cases": 6.0, "avg_unique_failure_types": 5.0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_model_pack_history_trend_v1",
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
            self.assertIn("avg_pack_quality_score_decreasing", (payload.get("trend") or {}).get("alerts", []))


if __name__ == "__main__":
    unittest.main()
