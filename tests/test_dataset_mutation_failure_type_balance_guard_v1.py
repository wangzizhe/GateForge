import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationFailureTypeBalanceGuardV1Tests(unittest.TestCase):
    def test_failure_type_balance_guard_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            records = root / "records.json"
            out = root / "summary.json"
            manifest.write_text(
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
            records.write_text(
                json.dumps(
                    {
                        "records": [
                            {"observed_failure_type": "simulate_error"},
                            {"observed_failure_type": "model_check_error"},
                            {"observed_failure_type": "semantic_regression"},
                            {"observed_failure_type": "numerical_instability"},
                            {"observed_failure_type": "constraint_violation"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_failure_type_balance_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-validation-records",
                    str(records),
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
            self.assertGreaterEqual(int(payload.get("expected_failure_type_count", 0)), 4)

    def test_failure_type_balance_guard_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_failure_type_balance_guard_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
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
