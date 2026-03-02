import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatDefensibilityHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_needs_review_on_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prev = root / "prev.json"
            curr = root / "curr.json"
            out = root / "summary.json"
            prev.write_text(json.dumps({"status": "PASS", "avg_defensibility_score": 80.0, "pass_rate_pct": 100.0, "publish_ready_streak": 2}), encoding="utf-8")
            curr.write_text(json.dumps({"status": "NEEDS_REVIEW", "avg_defensibility_score": 74.0, "pass_rate_pct": 50.0, "publish_ready_streak": 1}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_defensibility_history_trend_v1", "--previous", str(prev), "--current", str(curr), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")

    def test_trend_fail_on_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_defensibility_history_trend_v1", "--previous", str(root / "missing1.json"), "--current", str(root / "missing2.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
