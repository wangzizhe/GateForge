import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceEvidenceReleaseManifestTests(unittest.TestCase):
    def test_manifest_outputs_release_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / "p.json"
            f = root / "f.json"
            m = root / "m.json"
            s = root / "s.json"
            out = root / "out.json"
            p.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            f.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            m.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            s.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_governance_evidence_release_manifest", "--governance-decision-proofbook", str(p), "--moat-execution-forecast", str(f), "--model-scale-mix-guard", str(m), "--failure-supply-plan", str(s), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(isinstance(payload.get("release_ready"), bool))

    def test_manifest_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_governance_evidence_release_manifest", "--governance-decision-proofbook", str(Path(d) / "missing1.json"), "--moat-execution-forecast", str(Path(d) / "missing2.json"), "--model-scale-mix-guard", str(Path(d) / "missing3.json"), "--failure-supply-plan", str(Path(d) / "missing4.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
