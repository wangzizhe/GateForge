import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelExecutableTruthHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prev = root / "prev.json"
            curr = root / "curr.json"
            out = root / "summary.json"
            prev.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "latest_large_executable_real_count": 40,
                        "latest_large_executable_real_rate_pct": 88.0,
                        "latest_large_model_check_pass_rate_pct": 97.0,
                    }
                ),
                encoding="utf-8",
            )
            curr.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_large_executable_real_count": 32,
                        "latest_large_executable_real_rate_pct": 76.0,
                        "latest_large_model_check_pass_rate_pct": 90.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_executable_truth_history_trend_v1",
                    "--previous",
                    str(prev),
                    "--current",
                    str(curr),
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

    def test_trend_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_executable_truth_history_trend_v1",
                    "--previous",
                    str(root / "missing_prev.json"),
                    "--current",
                    str(root / "missing_curr.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
