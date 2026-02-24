import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutateTests(unittest.TestCase):
    def test_mutate_generates_manifest_and_pack(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "mutants"
            manifest = root / "manifest.json"
            pack = root / "pack.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutate",
                    "--out-dir",
                    str(out_dir),
                    "--manifest-out",
                    str(manifest),
                    "--pack-out",
                    str(pack),
                    "--backend",
                    "openmodelica_docker",
                    "--count",
                    "8",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            pack_payload = json.loads(pack.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload.get("total_cases"), 8)
            self.assertEqual(len(manifest_payload.get("cases", [])), 8)
            self.assertEqual(pack_payload.get("pack_id"), manifest_payload.get("pack_id"))
            self.assertEqual(len(pack_payload.get("cases", [])), 8)
            kinds = {str(c.get("mutation_type")) for c in manifest_payload.get("cases", [])}
            self.assertIn("script_parse_error", kinds)
            self.assertIn("model_check_error", kinds)
            self.assertIn("simulate_error", kinds)
            self.assertIn("semantic_regression", kinds)

    def test_mutate_mock_backend_expected_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutate",
                    "--out-dir",
                    str(root / "mutants"),
                    "--manifest-out",
                    str(root / "manifest.json"),
                    "--pack-out",
                    str(root / "pack.json"),
                    "--backend",
                    "mock",
                    "--count",
                    "4",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((root / "pack.json").read_text(encoding="utf-8"))
            for row in payload.get("cases", []):
                expected = row.get("expected", {})
                self.assertEqual(expected.get("gate"), "PASS")
                self.assertEqual(expected.get("failure_type"), "none")


if __name__ == "__main__":
    unittest.main()
