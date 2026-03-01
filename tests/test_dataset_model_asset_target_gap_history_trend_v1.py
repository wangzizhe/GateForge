import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelAssetTargetGapHistoryTrendV1Tests(unittest.TestCase):
    def test_history_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"
            previous.write_text(json.dumps({"status": "PASS", "avg_target_gap_score": 20.0, "avg_critical_gap_count": 0.0}), encoding="utf-8")
            current.write_text(json.dumps({"status": "NEEDS_REVIEW", "avg_target_gap_score": 26.0, "avg_critical_gap_count": 1.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_target_gap_history_trend_v1",
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
            self.assertIn("avg_target_gap_score_increasing", (payload.get("trend") or {}).get("alerts", []))


if __name__ == "__main__":
    unittest.main()
