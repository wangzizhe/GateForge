import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMilestoneCheckpointV1Tests(unittest.TestCase):
    def test_checkpoint_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            moat = root / "moat.json"
            scoreboard = root / "scoreboard.json"
            alignment = root / "alignment.json"
            release = root / "release.json"
            momentum = root / "momentum.json"
            out = root / "summary.json"
            moat.write_text(json.dumps({"status": "PASS", "metrics": {"moat_score": 84.0}}), encoding="utf-8")
            scoreboard.write_text(json.dumps({"status": "PASS", "moat_public_score": 86.0}), encoding="utf-8")
            alignment.write_text(json.dumps({"status": "PASS", "alignment_score": 88.0, "contradiction_count": 0}), encoding="utf-8")
            release.write_text(json.dumps({"status": "PASS", "release_candidate_score": 85.0, "candidate_decision": "GO"}), encoding="utf-8")
            momentum.write_text(
                json.dumps({"status": "PASS", "momentum_score": 82.0, "delta_total_real_models": 2, "delta_large_models": 1}),
                encoding="utf-8",
            )
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_milestone_checkpoint_v1", "--moat-trend-snapshot-summary", str(moat), "--moat-public-scoreboard-summary", str(scoreboard), "--snapshot-moat-alignment-summary", str(alignment), "--modelica-release-candidate-gate-summary", str(release), "--model-asset-momentum-summary", str(momentum), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("milestone_decision"), {"GO", "LIMITED_GO", "HOLD"})
            self.assertEqual(summary.get("model_asset_momentum_status"), "PASS")
            self.assertEqual(summary.get("delta_large_models"), 1)

    def test_checkpoint_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_milestone_checkpoint_v1", "--moat-trend-snapshot-summary", str(root / "m.json"), "--moat-public-scoreboard-summary", str(root / "s.json"), "--snapshot-moat-alignment-summary", str(root / "a.json"), "--modelica-release-candidate-gate-summary", str(root / "r.json"), "--model-asset-momentum-summary", str(root / "x.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
