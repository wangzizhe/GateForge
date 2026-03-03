import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationValidationMatrixV2Tests(unittest.TestCase):
    def test_validation_matrix_v2_builds_stratified_confusion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            records = root / "records.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"
            matrix = root / "matrix.json"

            records.write_text(
                json.dumps(
                    {
                        "mutation_records": [
                            {
                                "mutation_id": "m_medium_1",
                                "expected_failure_type": "simulate_error",
                                "observed_failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "observed_stage": "simulate",
                                "stage_match": True,
                                "type_match": True,
                            },
                            {
                                "mutation_id": "m_large_1",
                                "expected_failure_type": "semantic_regression",
                                "observed_failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "observed_stage": "simulate",
                                "stage_match": True,
                                "type_match": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m_medium_1", "target_scale": "medium"},
                            {"mutation_id": "m_large_1", "target_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v2",
                    "--validation-records",
                    str(records),
                    "--mutation-manifest",
                    str(manifest),
                    "--matrix-out",
                    str(matrix),
                    "--out",
                    str(out),
                    "--min-medium-type-match-rate-pct",
                    "10",
                    "--min-large-type-match-rate-pct",
                    "10",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            matrix_payload = json.loads(matrix.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int((summary.get("overall") or {}).get("validated_count", 0)), 2)
            self.assertEqual(int(((summary.get("by_scale") or {}).get("medium") or {}).get("validated_count", 0)), 1)
            self.assertEqual(int(((summary.get("by_scale") or {}).get("large") or {}).get("validated_count", 0)), 1)
            self.assertEqual(matrix_payload.get("schema_version"), "mutation_validation_matrix_v2")

    def test_validation_matrix_v2_fail_when_records_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_validation_matrix_v2",
                    "--validation-records",
                    str(root / "missing_records.json"),
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
