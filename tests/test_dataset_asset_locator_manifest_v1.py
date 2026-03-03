import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAssetLocatorManifestV1Tests(unittest.TestCase):
    def test_locator_manifest_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mroot = root / "models"
            uroot = root / "mutants"
            mroot.mkdir(parents=True, exist_ok=True)
            uroot.mkdir(parents=True, exist_ok=True)
            model_file = mroot / "A.mo"
            mutant_file = uroot / "A_mut.mo"
            model_file.write_text("model A\nend A;\n", encoding="utf-8")
            mutant_file.write_text("model A_mut\nend A_mut;\n", encoding="utf-8")

            registry = root / "registry.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"
            registry.write_text(json.dumps({"models": [{"asset_type": "model_source", "source_path": str(model_file)}]}), encoding="utf-8")
            manifest.write_text(json.dumps({"mutations": [{"mutated_model_path": str(mutant_file)}]}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_asset_locator_manifest_v1",
                    "--executable-registry",
                    str(registry),
                    "--mutation-manifest",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(payload.get("model_root_count", 0)), 1)
            self.assertGreaterEqual(int(payload.get("mutant_root_count", 0)), 1)

    def test_locator_manifest_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_asset_locator_manifest_v1",
                    "--executable-registry",
                    str(root / "missing_registry.json"),
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
