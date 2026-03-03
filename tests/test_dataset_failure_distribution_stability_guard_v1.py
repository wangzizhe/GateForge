import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionStabilityGuardV1Tests(unittest.TestCase):
    def test_guard_pass_on_balanced_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current_manifest = root / "current_manifest.json"
            previous_manifest = root / "previous_manifest.json"
            out = root / "summary.json"

            current_manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"expected_failure_type": "simulate_error", "target_scale": "large"},
                            {"expected_failure_type": "model_check_error", "target_scale": "large"},
                            {"expected_failure_type": "semantic_regression", "target_scale": "large"},
                            {"expected_failure_type": "numerical_instability", "target_scale": "large"},
                            {"expected_failure_type": "constraint_violation", "target_scale": "large"},
                            {"expected_failure_type": "simulate_error", "target_scale": "medium"},
                            {"expected_failure_type": "model_check_error", "target_scale": "medium"},
                            {"expected_failure_type": "semantic_regression", "target_scale": "medium"},
                            {"expected_failure_type": "numerical_instability", "target_scale": "medium"},
                            {"expected_failure_type": "constraint_violation", "target_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            previous_manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"expected_failure_type": "simulate_error"},
                            {"expected_failure_type": "model_check_error"},
                            {"expected_failure_type": "semantic_regression"},
                            {"expected_failure_type": "numerical_instability"},
                            {"expected_failure_type": "constraint_violation"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_stability_guard_v1",
                    "--current-mutation-manifest",
                    str(current_manifest),
                    "--previous-mutation-manifest",
                    str(previous_manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("unique_failure_types", 0)), 5)
            self.assertGreaterEqual(int(summary.get("large_failure_type_coverage", 0)), 5)

    def test_guard_fail_when_current_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_stability_guard_v1",
                    "--current-mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
