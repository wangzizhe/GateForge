import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionBenchmarkTests(unittest.TestCase):
    def test_pass_when_detection_improves_and_drift_controlled(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "summary.json"
            before.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"failure_type": "numerical_divergence", "model_scale": "small", "detected": True, "false_positive": False, "regressed": False},
                            {"failure_type": "solver_non_convergence", "model_scale": "medium", "detected": True, "false_positive": False, "regressed": False},
                            {"failure_type": "unit_parameter_mismatch", "model_scale": "large", "detected": False, "false_positive": False, "regressed": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"failure_type": "numerical_divergence", "model_scale": "small", "detected": True, "false_positive": False, "regressed": False},
                            {"failure_type": "solver_non_convergence", "model_scale": "medium", "detected": True, "false_positive": False, "regressed": False},
                            {"failure_type": "unit_parameter_mismatch", "model_scale": "large", "detected": True, "false_positive": False, "regressed": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_benchmark",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
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
            self.assertEqual(payload.get("alerts"), [])

    def test_needs_review_when_false_positive_and_regression_increase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "summary.json"
            before.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"failure_type": "numerical_divergence", "model_scale": "small", "detected": True, "false_positive": False, "regressed": False},
                            {"failure_type": "solver_non_convergence", "model_scale": "medium", "detected": True, "false_positive": False, "regressed": False},
                            {"failure_type": "stability_regression", "model_scale": "large", "detected": True, "false_positive": False, "regressed": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"failure_type": "numerical_divergence", "model_scale": "small", "detected": True, "false_positive": True, "regressed": True},
                            {"failure_type": "solver_non_convergence", "model_scale": "medium", "detected": False, "false_positive": True, "regressed": True},
                            {"failure_type": "boundary_condition_drift", "model_scale": "small", "detected": False, "false_positive": False, "regressed": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_benchmark",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
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
            self.assertIn("false_positive_rate_increase_exceeds_threshold", payload.get("alerts", []))
            self.assertIn("regression_rate_exceeds_threshold", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
