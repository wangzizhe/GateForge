import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaAssetUniquenessIndexV1Tests(unittest.TestCase):
    def test_uniqueness_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            summary = root / "lib_summary.json"
            out = root / "summary.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "checksum_sha256": "a", "source_name": "s1", "source_path": "a.mo"},
                            {"model_id": "m2", "asset_type": "model_source", "checksum_sha256": "b", "source_name": "s2", "source_path": "b.mo"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            summary.write_text(json.dumps({"registry_path": str(registry)}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_asset_uniqueness_index_v1",
                    "--modelica-library-registry-summary",
                    str(summary),
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

    def test_uniqueness_fail_when_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_asset_uniqueness_index_v1",
                    "--modelica-library-registry-summary",
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
