import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationMismatchTriageDatasetV1Tests(unittest.TestCase):
    def test_triage_dataset_groups_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            records = root / "records.json"
            manifest = root / "manifest.json"
            dataset_out = root / "triage.json"
            out = root / "summary.json"

            records.write_text(
                json.dumps(
                    {
                        "mutation_records": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "simulate_error",
                                "observed_failure_type": "model_check_error",
                                "expected_stage": "simulate",
                                "observed_stage": "check",
                                "stage_match": False,
                                "type_match": False,
                            },
                            {
                                "mutation_id": "m2",
                                "expected_failure_type": "simulate_error",
                                "observed_failure_type": "model_check_error",
                                "expected_stage": "simulate",
                                "observed_stage": "check",
                                "stage_match": False,
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
                            {"mutation_id": "m1", "target_scale": "large", "operator_family": "model_integrity", "operator": "inject_undefined_symbol_equation"},
                            {"mutation_id": "m2", "target_scale": "large", "operator_family": "model_integrity", "operator": "inject_undefined_symbol_equation"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_mismatch_triage_dataset_v1",
                    "--validation-records",
                    str(records),
                    "--mutation-manifest",
                    str(manifest),
                    "--triage-dataset-out",
                    str(dataset_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            dataset = json.loads(dataset_out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertEqual(int(payload.get("mismatch_count", 0)), 2)
            rows = dataset.get("rows") if isinstance(dataset.get("rows"), list) else []
            self.assertEqual(len(rows), 1)
            self.assertEqual(int(rows[0].get("count", 0)), 2)

    def test_triage_dataset_fail_when_records_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_mismatch_triage_dataset_v1",
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
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
