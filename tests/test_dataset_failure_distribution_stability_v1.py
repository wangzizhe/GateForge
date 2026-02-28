import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionStabilityV1Tests(unittest.TestCase):
    def test_stability_pass_when_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"
            previous.write_text(
                json.dumps(
                    {
                        "distribution_drift_score": 0.12,
                        "regression_rate_after": 0.08,
                        "distribution": {"failure_type_after": {"simulate_error": 4, "solver_non_convergence": 1}},
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "distribution_drift_score": 0.14,
                        "regression_rate_after": 0.09,
                        "distribution": {"failure_type_after": {"simulate_error": 5, "solver_non_convergence": 1}},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_stability_v1",
                    "--current-benchmark-summary",
                    str(current),
                    "--previous-benchmark-summary",
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
            self.assertEqual(payload.get("status"), "PASS")

    def test_stability_needs_review_when_drift_increase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"
            previous.write_text(
                json.dumps(
                    {
                        "distribution_drift_score": 0.1,
                        "regression_rate_after": 0.08,
                        "distribution": {"failure_type_after": {"simulate_error": 5, "solver_non_convergence": 1}},
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "distribution_drift_score": 0.25,
                        "regression_rate_after": 0.18,
                        "distribution": {"failure_type_after": {"simulate_error": 6}},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_stability_v1",
                    "--current-benchmark-summary",
                    str(current),
                    "--previous-benchmark-summary",
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
            self.assertIn("distribution_drift_score_increasing", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
