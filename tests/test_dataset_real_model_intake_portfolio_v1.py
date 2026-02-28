import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelIntakePortfolioV1Tests(unittest.TestCase):
    def test_portfolio_pass(self) -> None:
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
                                "suggested_scale": "medium",
                                "license_tag": "MIT",
                                "provenance": {"source_url": "https://github.com/org/repo/m1.mo"},
                            },
                            {
                                "model_id": "m2",
                                "suggested_scale": "large",
                                "license_tag": "Apache-2.0",
                                "provenance": {"source_url": "https://gitlab.com/org/repo/m2.mo"},
                            },
                            {
                                "model_id": "m3",
                                "suggested_scale": "small",
                                "license_tag": "BSD-3-Clause",
                                "provenance": {"source_url": "https://example.org/m3.mo"},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_portfolio_v1",
                    "--real-model-registry",
                    str(registry),
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
            self.assertEqual(payload.get("total_real_models"), 3)
            self.assertEqual(payload.get("large_models"), 1)

    def test_portfolio_fail_when_missing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_portfolio_v1",
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
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
