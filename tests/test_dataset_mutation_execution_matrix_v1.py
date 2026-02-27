import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationExecutionMatrixV1Tests(unittest.TestCase):
    def test_matrix_pass_when_all_cells_executed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            obs = root / "obs.json"
            matrix_out = root / "matrix.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "mdl_medium", "suggested_scale": "medium"},
                            {"model_id": "mdl_large", "suggested_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_model_id": "mdl_medium", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "target_model_id": "mdl_large", "expected_failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            obs.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "observed_failure_types": ["simulate_error", "simulate_error"]},
                            {"mutation_id": "m2", "observed_failure_types": ["semantic_regression", "semantic_regression"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_matrix_v1",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--replay-observations",
                    str(obs),
                    "--matrix-out",
                    str(matrix_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            matrix = json.loads(matrix_out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(matrix.get("schema_version"), "mutation_execution_matrix_v1")

    def test_matrix_needs_review_when_cells_unexecuted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            obs = root / "obs.json"
            out = root / "summary.json"

            registry.write_text(json.dumps({"models": [{"model_id": "mdl_medium", "suggested_scale": "medium"}]}), encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_model_id": "mdl_medium", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "target_model_id": "mdl_medium", "expected_failure_type": "model_check_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            obs.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "observed_failure_types": ["simulate_error", "simulate_error"]}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_matrix_v1",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--replay-observations",
                    str(obs),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertIn("matrix_has_unexecuted_cells", summary.get("alerts", []))

    def test_matrix_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_matrix_v1",
                    "--real-model-registry",
                    str(root / "missing_registry.json"),
                    "--validated-mutation-manifest",
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
