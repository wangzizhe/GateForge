import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionGuardSnapshotV1Tests(unittest.TestCase):
    def test_guard_snapshot_builds_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            guard = root / "guard.json"
            weekly = root / "weekly.json"
            out = root / "summary.json"

            guard.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "distribution_drift_tvd": 0.08,
                        "failure_type_entropy": 2.1,
                        "unique_failure_types": 5,
                    }
                ),
                encoding="utf-8",
            )
            weekly.write_text(
                json.dumps({"kpis": {"failure_distribution_stability_score": 82.0}}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_guard_snapshot_v1",
                    "--failure-distribution-stability-guard-summary",
                    str(guard),
                    "--weekly-summary",
                    str(weekly),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(float(payload.get("stability_score", 0.0)), 0.0)
            self.assertGreaterEqual(float(payload.get("rare_failure_replay_rate", 0.0)), 0.5)

    def test_guard_snapshot_fail_on_missing_guard(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_guard_snapshot_v1",
                    "--failure-distribution-stability-guard-summary",
                    str(root / "missing_guard.json"),
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
