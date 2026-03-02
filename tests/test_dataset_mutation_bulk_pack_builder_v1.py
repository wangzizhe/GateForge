import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationBulkPackBuilderV1Tests(unittest.TestCase):
    def test_builder_generates_scaled_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            out = root / "summary.json"
            manifest = root / "manifest.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m_large", "asset_type": "model_source", "suggested_scale": "large", "source_path": "a.mo"},
                            {"model_id": "m_medium", "asset_type": "model_source", "suggested_scale": "medium", "source_path": "b.mo"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_bulk_pack_builder_v1",
                    "--model-registry",
                    str(registry),
                    "--failure-types",
                    "simulate_error,model_check_error",
                    "--mutations-per-failure-type",
                    "2",
                    "--manifest-out",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(summary.get("total_mutations", 0)), 8)

    def test_builder_fail_when_registry_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_bulk_pack_builder_v1",
                    "--model-registry",
                    str(root / "missing.json"),
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
