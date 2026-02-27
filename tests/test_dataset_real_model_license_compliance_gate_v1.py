import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelLicenseComplianceGateV1Tests(unittest.TestCase):
    def test_license_gate_pass_with_valid_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            out = root / "summary.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "m1",
                                "license_tag": "MIT",
                                "source_path": "m1.mo",
                                "checksum_sha256": "abc",
                                "reproducibility": {"repro_command": "omc m1.mo"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_license_compliance_gate_v1",
                    "--real-model-registry",
                    str(registry),
                    "--max-unknown-license-ratio-pct",
                    "50",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")

    def test_license_gate_fail_when_registry_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_license_compliance_gate_v1",
                    "--real-model-registry",
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
