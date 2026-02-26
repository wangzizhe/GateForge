import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionBenchmarkV2Tests(unittest.TestCase):
    def test_benchmark_v2_pass_with_balanced_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            validator = root / "validator.json"
            validated = root / "validated.json"
            out = root / "summary.json"

            baseline.write_text(
                json.dumps(
                    {
                        "selected_cases": [
                            {"failure_type": "a", "model_scale": "small"},
                            {"failure_type": "b", "model_scale": "medium"},
                            {"failure_type": "c", "model_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            validator.write_text(json.dumps({"total_mutations": 4, "validated_count": 4, "uncertain_count": 0, "expected_match_ratio_pct": 90.0}), encoding="utf-8")
            validated.write_text(
                json.dumps(
                    {
                        "schema_version": "validated_mutation_manifest_v1",
                        "mutations": [
                            {"target_scale": "large", "expected_failure_type": "c", "observed_majority_failure_type": "c"},
                            {"target_scale": "medium", "expected_failure_type": "b", "observed_majority_failure_type": "b"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_benchmark_v2",
                    "--failure-baseline-pack",
                    str(baseline),
                    "--mutation-validator-summary",
                    str(validator),
                    "--validated-mutation-manifest",
                    str(validated),
                    "--max-failure-type-drift",
                    "0.9",
                    "--max-model-scale-drift",
                    "0.9",
                    "--min-large-share-after-pct",
                    "10",
                    "--min-validated-match-ratio-pct",
                    "70",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(summary.get("total_cases_after", 0)), 1)

    def test_benchmark_v2_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_benchmark_v2",
                    "--failure-baseline-pack",
                    str(root / "missing_baseline.json"),
                    "--mutation-validator-summary",
                    str(root / "missing_validator.json"),
                    "--validated-mutation-manifest",
                    str(root / "missing_validated.json"),
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
