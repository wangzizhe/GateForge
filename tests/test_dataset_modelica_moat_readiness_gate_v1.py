import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaMoatReadinessGateV1Tests(unittest.TestCase):
    def test_moat_gate_pass_when_components_strong(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            lic = root / "lic.json"
            rec = root / "rec.json"
            yld = root / "yld.json"
            back = root / "back.json"
            out = root / "summary.json"
            lic.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            rec.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            yld.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            back.write_text(json.dumps({"status": "PASS", "p0_count": 0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_moat_readiness_gate_v1",
                    "--real-model-license-compliance-summary",
                    str(lic),
                    "--modelica-mutation-recipe-library-summary",
                    str(rec),
                    "--real-model-failure-yield-summary",
                    str(yld),
                    "--real-model-intake-backlog-summary",
                    str(back),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("release_recommendation"), {"GO", "LIMITED_GO", "HOLD"})
            self.assertIn(summary.get("confidence_level"), {"low", "medium", "high"})
            self.assertIn("critical_blockers", summary)

    def test_moat_gate_fail_when_required_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_moat_readiness_gate_v1",
                    "--real-model-license-compliance-summary",
                    str(root / "missing_lic.json"),
                    "--modelica-mutation-recipe-library-summary",
                    str(root / "missing_rec.json"),
                    "--real-model-failure-yield-summary",
                    str(root / "missing_yld.json"),
                    "--real-model-intake-backlog-summary",
                    str(root / "missing_back.json"),
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
