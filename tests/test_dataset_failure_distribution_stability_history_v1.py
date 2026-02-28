import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionStabilityHistoryV1Tests(unittest.TestCase):
    def test_history_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            out = root / "summary.json"
            r1.write_text(json.dumps({"status": "PASS", "stability_score": 82.0, "distribution_drift_score": 0.14, "rare_failure_replay_rate": 1.0}), encoding="utf-8")
            r2.write_text(json.dumps({"status": "NEEDS_REVIEW", "stability_score": 73.0, "distribution_drift_score": 0.23, "rare_failure_replay_rate": 0.5}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_stability_history_v1",
                    "--record",
                    str(r1),
                    "--record",
                    str(r2),
                    "--ledger",
                    str(root / "history.jsonl"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 2)


if __name__ == "__main__":
    unittest.main()
