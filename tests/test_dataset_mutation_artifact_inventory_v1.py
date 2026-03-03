import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationArtifactInventoryV1Tests(unittest.TestCase):
    def test_inventory_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            mutants = root / "mutants"
            mutants.mkdir(parents=True, exist_ok=True)
            m1 = mutants / "m1.mo"
            m2 = mutants / "m2.mo"
            m1.write_text("model M1\nend M1;\n", encoding="utf-8")
            m2.write_text("model M2\nend M2;\n", encoding="utf-8")

            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutated_model_path": str(m1), "expected_failure_type": "simulate_error", "target_scale": "large"},
                            {"mutated_model_path": str(m2), "expected_failure_type": "model_check_error", "target_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "1", "execution_status": "EXECUTED"},
                            {"mutation_id": "2", "execution_status": "EXECUTED"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_artifact_inventory_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
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
            self.assertEqual(int(payload.get("missing_mutant_files", 0)), 0)

    def test_inventory_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_artifact_inventory_v1",
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
