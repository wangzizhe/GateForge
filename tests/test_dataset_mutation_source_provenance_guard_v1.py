import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSourceProvenanceGuardV1Tests(unittest.TestCase):
    def test_guard_pass_with_existing_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models_root = root / "models"
            models_root.mkdir(parents=True, exist_ok=True)
            model_a = models_root / "A.mo"
            model_a.write_text("model A\nend A;\n", encoding="utf-8")
            model_b = models_root / "B.mo"
            model_b.write_text("model B\nend B;\n", encoding="utf-8")
            manifest = root / "manifest.json"
            registry = root / "registry.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_model_id": "mdl_a", "source_model_path": str(model_a)},
                            {"mutation_id": "m2", "target_model_id": "mdl_b", "source_model_path": str(model_b)},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "mdl_a"},
                            {"model_id": "mdl_b"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_source_provenance_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--executable-registry",
                    str(registry),
                    "--allowed-model-roots",
                    str(models_root),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")

    def test_guard_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_source_provenance_guard_v1",
                    "--mutation-manifest",
                    str(root / "missing.json"),
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
