import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelAssetDiscoveryV1Tests(unittest.TestCase):
    def test_discovery_outputs_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models = root / "models"
            models.mkdir(parents=True, exist_ok=True)
            (models / "m1.mo").write_text("model M1\n Real x;\n equation\n der(x)=1;\nend M1;\n", encoding="utf-8")
            (models / "m2.mo").write_text("model M2\n Real x;\n equation\n der(x)=2;\nend M2;\n", encoding="utf-8")
            out = root / "summary.json"
            catalog = root / "catalog.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_asset_discovery_v1",
                    "--model-root",
                    str(models),
                    "--license-tag",
                    "Apache-2.0",
                    "--catalog-out",
                    str(catalog),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(summary.get("total_candidates", 0)), 2)
            payload = json.loads(catalog.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(payload.get("candidates") or []), 2)

    def test_discovery_needs_review_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            empty = root / "empty"
            empty.mkdir(parents=True, exist_ok=True)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_asset_discovery_v1",
                    "--model-root",
                    str(empty),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
