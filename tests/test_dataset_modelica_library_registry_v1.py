import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaLibraryRegistryV1Tests(unittest.TestCase):
    def test_registry_discovers_assets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models = root / "models"
            models.mkdir(parents=True, exist_ok=True)
            (models / "small_probe.mo").write_text("model SmallProbe\n  Real x;\nequation\n  der(x) = -x;\nend SmallProbe;\n", encoding="utf-8")
            (models / "medium_probe.mo").write_text("model MediumProbe\n  Real x;\n  Real y;\nequation\n  der(x)=y;\n  der(y)=-x;\nend MediumProbe;\n", encoding="utf-8")
            (models / "large_probe.mos").write_text("loadFile(\"LargeProbe.mo\");\n", encoding="utf-8")

            registry_out = root / "registry.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_library_registry_v1",
                    "--model-root",
                    str(models),
                    "--registry-out",
                    str(registry_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            registry = json.loads(registry_out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(summary.get("total_assets", 0)), 3)
            self.assertEqual(registry.get("schema_version"), "modelica_library_registry_v1")

    def test_registry_fails_when_no_assets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_library_registry_v1",
                    "--model-root",
                    str(root / "missing_models"),
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
