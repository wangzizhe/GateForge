import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelFamilyCoverageBoardV1Tests(unittest.TestCase):
    def test_family_coverage_board_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reg = root / "registry.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"
            reg.write_text(
                json.dumps(
                    {
                        "models": [
                            {"asset_type": "model_source", "model_id": "m1", "source_path": "/tmp/fluid/Pipe.mo", "suggested_scale": "large"},
                            {"asset_type": "model_source", "model_id": "m2", "source_path": "/tmp/thermal/Heater.mo", "suggested_scale": "medium"},
                            {"asset_type": "model_source", "model_id": "m3", "source_path": "/tmp/electrical/Circuit.mo", "suggested_scale": "medium"},
                            {"asset_type": "model_source", "model_id": "m4", "source_path": "/tmp/mechanical/Gear.mo", "suggested_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps({"mutations": [{"target_model_id": "m1"}, {"target_model_id": "m2"}, {"target_model_id": "m3"}]}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_family_coverage_board_v1",
                    "--executable-registry",
                    str(reg),
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
            self.assertGreaterEqual(int(payload.get("covered_families", 0)), 3)

    def test_family_coverage_board_fail_when_missing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_family_coverage_board_v1",
                    "--executable-registry",
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
