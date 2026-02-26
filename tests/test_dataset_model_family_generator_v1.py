import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelFamilyGeneratorV1Tests(unittest.TestCase):
    def test_family_generator_builds_families(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "modelica_library_registry_v1",
                        "models": [
                            {"model_id": "m1", "source_path": "x/probe_small.mo", "suggested_scale": "small"},
                            {"model_id": "m2", "source_path": "x/probe_medium.mo", "suggested_scale": "medium"},
                            {"model_id": "m3", "source_path": "x/probe_large.mo", "suggested_scale": "large"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_family_generator_v1",
                    "--modelica-library-registry",
                    str(registry),
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
            self.assertGreaterEqual(int(summary.get("total_families", 0)), 1)

    def test_family_generator_fails_without_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_family_generator_v1",
                    "--modelica-library-registry",
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
