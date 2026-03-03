import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSignatureUniquenessGuardV1Tests(unittest.TestCase):
    def test_guard_needs_review_on_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "mutation_manifest.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_model_id": "mdl_a", "failure_type": "simulate_error", "operator": "op_a", "seed": 1},
                            {"mutation_id": "m2", "target_model_id": "mdl_a", "failure_type": "simulate_error", "operator": "op_a", "seed": 1},
                            {"mutation_id": "m3", "target_model_id": "mdl_b", "failure_type": "model_check_error", "operator": "op_b", "seed": 2},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_signature_uniqueness_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--min-unique-signature-ratio-pct",
                    "90",
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
            self.assertEqual(int(payload.get("duplicate_signatures", 0)), 1)

    def test_guard_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_signature_uniqueness_guard_v1",
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
