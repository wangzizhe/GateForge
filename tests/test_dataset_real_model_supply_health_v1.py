import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelSupplyHealthV1Tests(unittest.TestCase):
    def test_supply_health_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            lic = root / "lic.json"
            back = root / "back.json"
            yld = root / "yield.json"
            out = root / "summary.json"
            intake.write_text(json.dumps({"status": "PASS", "accepted_count": 4}), encoding="utf-8")
            lic.write_text(json.dumps({"status": "PASS", "license_risk_score": 8.0}), encoding="utf-8")
            back.write_text(json.dumps({"status": "PASS", "p0_count": 0}), encoding="utf-8")
            yld.write_text(json.dumps({"status": "PASS", "effective_yield_score": 82.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_supply_health_v1",
                    "--real-model-intake-summary",
                    str(intake),
                    "--real-model-license-compliance-summary",
                    str(lic),
                    "--real-model-intake-backlog-summary",
                    str(back),
                    "--real-model-failure-yield-summary",
                    str(yld),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn("supply_health_score", summary)

    def test_supply_health_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_supply_health_v1",
                    "--real-model-intake-summary",
                    str(root / "missing_intake.json"),
                    "--real-model-license-compliance-summary",
                    str(root / "missing_lic.json"),
                    "--real-model-intake-backlog-summary",
                    str(root / "missing_back.json"),
                    "--real-model-failure-yield-summary",
                    str(root / "missing_yield.json"),
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
