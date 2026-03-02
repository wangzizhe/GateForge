import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelAssetInventoryReportV1Tests(unittest.TestCase):
    def test_inventory_report_builds_scale_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models = root / "models"
            models.mkdir(parents=True, exist_ok=True)

            small = models / "small.mo"
            small.write_text("model Small\n  Real x;\nend Small;\n", encoding="utf-8")

            medium = models / "medium.mo"
            medium.write_text("\n".join(["model Medium"] + [f"  Real x{i};" for i in range(70)] + ["end Medium;"]), encoding="utf-8")

            large = models / "large.mo"
            large.write_text("\n".join(["model Large"] + [f"  Real x{i};" for i in range(150)] + ["end Large;"]), encoding="utf-8")

            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_inventory_report_v1",
                    "--model-glob",
                    str(models / "*.mo"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            by_scale = payload.get("by_scale") if isinstance(payload.get("by_scale"), dict) else {}
            self.assertEqual(int(payload.get("total_models", 0)), 3)
            self.assertEqual(int(by_scale.get("small", 0)), 1)
            self.assertEqual(int(by_scale.get("medium", 0)), 1)
            self.assertEqual(int(by_scale.get("large", 0)), 1)

    def test_inventory_report_fails_without_models(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_inventory_report_v1",
                    "--model-glob",
                    str(root / "*.mo"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
