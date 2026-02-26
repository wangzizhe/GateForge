import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceDecisionProofbookTests(unittest.TestCase):
    def test_proofbook_builds_decision(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            e = root / "e.json"
            f = root / "f.json"
            t = root / "t.json"
            x = root / "x.json"
            out = root / "out.json"
            e.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            f.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            t.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            x.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_governance_decision_proofbook", "--governance-evidence-pack", str(e), "--moat-execution-forecast", str(f), "--pack-execution-tracker", str(t), "--policy-experiment-runner", str(x), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            p = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(p.get("decision"), {"PROMOTE", "PROMOTE_WITH_GUARDS", "HOLD"})

    def test_proofbook_fails_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_governance_decision_proofbook", "--governance-evidence-pack", str(Path(d) / "missing1.json"), "--moat-execution-forecast", str(Path(d) / "missing2.json"), "--pack-execution-tracker", str(Path(d) / "missing3.json"), "--policy-experiment-runner", str(Path(d) / "missing4.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
