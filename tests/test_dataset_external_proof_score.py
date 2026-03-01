import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetExternalProofScoreTests(unittest.TestCase):
    def test_proof_score_outputs_numeric_score(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m = root / "m.json"
            f = root / "f.json"
            ms = root / "ms.json"
            p = root / "p.json"
            out = root / "out.json"
            m.write_text(json.dumps({"release_ready": True, "artifacts": [{"name": "x"}]}), encoding="utf-8")
            f.write_text(json.dumps({"projected_moat_score_30d": 70.0}), encoding="utf-8")
            ms.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "execution_readiness_index": 82.0,
                            "target_gap_pressure_index": 76.5,
                            "model_asset_target_gap_score": 28.5,
                        }
                    }
                ),
                encoding="utf-8",
            )
            p.write_text(json.dumps({"decision": "PROMOTE"}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_external_proof_score", "--evidence-release-manifest", str(m), "--moat-execution-forecast", str(f), "--moat-trend-snapshot-summary", str(ms), "--governance-decision-proofbook", str(p), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsInstance(payload.get("proof_score"), float)
            self.assertIsInstance(payload.get("execution_readiness_index"), float)
            self.assertIsInstance(payload.get("target_gap_pressure_index"), float)
            self.assertIsInstance(payload.get("model_asset_target_gap_score"), float)

    def test_proof_score_fail_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_external_proof_score", "--evidence-release-manifest", str(Path(d) / "missing1.json"), "--moat-execution-forecast", str(Path(d) / "missing2.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
