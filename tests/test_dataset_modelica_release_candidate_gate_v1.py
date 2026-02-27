import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaReleaseCandidateGateV1Tests(unittest.TestCase):
    def test_release_candidate_gate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            supply = root / "supply.json"
            audit = root / "audit.json"
            moat = root / "moat.json"
            out = root / "summary.json"
            supply.write_text(json.dumps({"status": "PASS", "supply_health_score": 84.0, "supply_gap_count": 0}), encoding="utf-8")
            audit.write_text(json.dumps({"status": "PASS", "execution_coverage_pct": 82.0, "missing_recipe_count": 1}), encoding="utf-8")
            moat.write_text(json.dumps({"status": "PASS", "moat_readiness_score": 85.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_release_candidate_gate_v1",
                    "--real-model-supply-health-summary",
                    str(supply),
                    "--mutation-recipe-execution-audit-summary",
                    str(audit),
                    "--modelica-moat-readiness-gate-summary",
                    str(moat),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("candidate_decision"), {"GO", "LIMITED_GO", "HOLD"})

    def test_release_candidate_gate_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_release_candidate_gate_v1",
                    "--real-model-supply-health-summary",
                    str(root / "missing_supply.json"),
                    "--mutation-recipe-execution-audit-summary",
                    str(root / "missing_audit.json"),
                    "--modelica-moat-readiness-gate-summary",
                    str(root / "missing_moat.json"),
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
