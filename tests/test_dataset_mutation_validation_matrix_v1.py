import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationValidationMatrixV1Tests(unittest.TestCase):
    def test_validation_matrix_pass_for_check_stage_match(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_model = root / "Source.mo"
            source_model.write_text(
                "model Source\n  Real x;\nequation\n  der(x) = -x;\nend Source;\n",
                encoding="utf-8",
            )

            mutant = root / "mutant_bad.mo"
            mutant.write_text(
                "model MutantBad\n  Real x;\nequation\n  der(x) = -x;\n",
                encoding="utf-8",
            )

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_manifest_v2_materialized",
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "model_check_error",
                                "expected_stage": "check",
                                "source_model_path": str(source_model),
                                "mutated_model_path": str(mutant),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            records = root / "records.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--backend",
                    "syntax",
                    "--min-stage-match-rate-pct",
                    "100",
                    "--min-type-match-rate-pct",
                    "100",
                    "--records-out",
                    str(records),
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
            self.assertEqual(summary.get("validation_backend_used"), "syntax")
            self.assertEqual(float(summary.get("baseline_check_pass_rate_pct", 0.0)), 100.0)
            self.assertEqual(float(summary.get("stage_match_rate_pct", 0.0)), 100.0)
            self.assertEqual(float(summary.get("type_match_rate_pct", 0.0)), 100.0)

    def test_validation_matrix_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("mutation_manifest_missing", summary.get("reasons") or [])


if __name__ == "__main__":
    unittest.main()
