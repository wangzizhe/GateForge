import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelSynthesizerV1Tests(unittest.TestCase):
    def test_synthesizer_generates_large_models(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / "medium_probe.mo").write_text(
                "model MediumProbe\n  Real x;\n  Real y;\nequation\n  der(x)=y;\n  der(y)=-x;\nend MediumProbe;\n",
                encoding="utf-8",
            )
            registry = root / "registry.json"
            registry_after = root / "registry_after.json"
            out = root / "summary.json"
            synth_dir = root / "synth"

            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "modelica_library_registry_v1",
                        "models": [
                            {
                                "model_id": "mdl_medium",
                                "asset_type": "model_source",
                                "source_path": str(src / "medium_probe.mo"),
                                "license_tag": "Apache-2.0",
                                "suggested_scale": "medium",
                                "reproducibility": {"om_version": "openmodelica-1.25.5"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_synthesizer_v1",
                    "--modelica-library-registry",
                    str(registry),
                    "--target-new-large-models",
                    "2",
                    "--synth-model-dir",
                    str(synth_dir),
                    "--registry-out",
                    str(registry_after),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(summary.get("synthesized_count", 0)), 1)
            self.assertGreaterEqual(int(summary.get("total_large_assets_after", 0)), 1)
            self.assertTrue(any(synth_dir.glob("*.mo")))

    def test_synthesizer_fails_without_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_synthesizer_v1",
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
