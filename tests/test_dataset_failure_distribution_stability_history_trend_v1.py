import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionStabilityHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_needs_review_on_worsen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"
            previous.write_text(json.dumps({"status": "PASS", "avg_stability_score": 82.0, "avg_distribution_drift_score": 0.14, "avg_rare_failure_replay_rate": 0.9}), encoding="utf-8")
            current.write_text(json.dumps({"status": "NEEDS_REVIEW", "avg_stability_score": 74.0, "avg_distribution_drift_score": 0.24, "avg_rare_failure_replay_rate": 0.6}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_stability_history_trend_v1",
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


if __name__ == "__main__":
    unittest.main()
