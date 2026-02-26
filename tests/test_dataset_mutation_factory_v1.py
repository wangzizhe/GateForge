import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationFactoryV1Tests(unittest.TestCase):
    def test_mutation_factory_generates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            families = root / "families.json"
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"

            families.write_text(
                json.dumps(
                    {
                        "schema_version": "model_family_manifest_v1",
                        "families": [
                            {
                                "family_id": "family_probe",
                                "member_model_ids": ["m_small", "m_medium", "m_large"],
                                "scale_map": {
                                    "small": "m_small",
                                    "medium": "m_medium",
                                    "large": "m_large",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "modelica_library_registry_v1",
                        "models": [
                            {"model_id": "m_small", "source_path": "x/small.mo", "suggested_scale": "small"},
                            {"model_id": "m_medium", "source_path": "x/medium.mo", "suggested_scale": "medium"},
                            {"model_id": "m_large", "source_path": "x/large.mo", "suggested_scale": "large"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_factory_v1",
                    "--model-family-manifest",
                    str(families),
                    "--modelica-library-registry",
                    str(registry),
                    "--mutations-per-model",
                    "4",
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
            self.assertGreaterEqual(int(summary.get("total_mutations", 0)), 12)
            self.assertGreaterEqual(int(summary.get("unique_failure_types", 0)), 4)

    def test_mutation_factory_fails_without_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_factory_v1",
                    "--model-family-manifest",
                    str(root / "missing_family.json"),
                    "--modelica-library-registry",
                    str(root / "missing_registry.json"),
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
