import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationFailureSignalAuthenticityHistoryTrendV1Tests(unittest.TestCase):
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
                        "latest_failure_signal_ratio_pct": 40.0,
                        "latest_expected_failure_type_signal_coverage_pct": 70.0,
                    }
                ),
                encoding="utf-8",
            )
            curr.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_failure_signal_ratio_pct": 20.0,
                        "latest_expected_failure_type_signal_coverage_pct": 40.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_failure_signal_authenticity_history_trend_v1",
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

    def test_trend_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_failure_signal_authenticity_history_trend_v1",
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
