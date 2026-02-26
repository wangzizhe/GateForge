import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationExecutionValidatorV1Tests(unittest.TestCase):
    def test_validator_pass_with_high_match(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            obs = root / "obs.json"
            validated = root / "validated.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_manifest_v1",
                        "mutations": [
                            {"mutation_id": "m1", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "expected_failure_type": "model_check_error"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            obs.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "observed_failure_types": ["simulate_error", "simulate_error", "simulate_error"]},
                            {"mutation_id": "m2", "observed_failure_types": ["model_check_error", "model_check_error", "model_check_error"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_validator_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--replay-observations",
                    str(obs),
                    "--validated-manifest-out",
                    str(validated),
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
            self.assertEqual(int(summary.get("validated_count", 0)), 2)

    def test_validator_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_validator_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--replay-observations",
                    str(root / "missing_obs.json"),
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
