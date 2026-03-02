import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaRepresentativenessGateV1Tests(unittest.TestCase):
    def test_gate_needs_review_on_low_representativeness(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            library_summary = root / "library.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "source_name": "s1", "suggested_scale": "small", "complexity": {"complexity_score": 30}},
                            {"model_id": "m2", "asset_type": "model_source", "source_name": "s1", "suggested_scale": "medium", "complexity": {"complexity_score": 70}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            library_summary.write_text(json.dumps({"status": "PASS", "registry_path": str(registry), "total_assets": 2}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_representativeness_gate_v1",
                    "--modelica-library-registry-summary",
                    str(library_summary),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("representativeness_score", payload)

    def test_gate_fail_when_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_representativeness_gate_v1",
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
