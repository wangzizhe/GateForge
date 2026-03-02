import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatExecutionCadenceHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prev = root / "prev.json"
            curr = root / "curr.json"
            out = root / "summary.json"
            prev.write_text(json.dumps({"status": "PASS", "avg_execution_cadence_score": 79.0, "avg_weekly_model_target": 3.0}), encoding="utf-8")
            curr.write_text(json.dumps({"status": "NEEDS_REVIEW", "avg_execution_cadence_score": 73.0, "avg_weekly_model_target": 2.0}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_execution_cadence_history_trend_v1", "--previous", str(prev), "--current", str(curr), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")

    def test_trend_fail_on_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_execution_cadence_history_trend_v1", "--previous", str(root / "m1.json"), "--current", str(root / "m2.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
