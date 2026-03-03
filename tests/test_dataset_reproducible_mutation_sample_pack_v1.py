import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetReproducibleMutationSamplePackV1Tests(unittest.TestCase):
    def test_sample_pack_pass(self) -> None:
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
            pack = root / "pack.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "a", "mutated_model_path": str(m1), "expected_failure_type": "simulate_error"},
                            {"mutation_id": "b", "mutated_model_path": str(m2), "expected_failure_type": "model_check_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "a", "execution_status": "EXECUTED"},
                            {"mutation_id": "b", "execution_status": "EXECUTED"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_reproducible_mutation_sample_pack_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
                    "--sample-size",
                    "1",
                    "--pack-out",
                    str(pack),
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
            self.assertEqual(int(payload.get("sampled_mutations", 0)), 1)
            self.assertTrue(pack.exists())

    def test_sample_pack_fail_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_reproducible_mutation_sample_pack_v1",
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
