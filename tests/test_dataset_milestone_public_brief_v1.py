import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMilestonePublicBriefV1Tests(unittest.TestCase):
    def test_public_brief_generated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            checkpoint = root / "checkpoint.json"
            scoreboard = root / "scoreboard.json"
            alignment = root / "alignment.json"
            out = root / "brief.json"
            checkpoint.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "milestone_decision": "GO",
                        "checkpoint_score": 85.0,
                        "model_asset_momentum_status": "PASS",
                        "model_asset_momentum_score": 82.0,
                        "delta_total_real_models": 2,
                        "delta_large_models": 1,
                    }
                ),
                encoding="utf-8",
            )
            scoreboard.write_text(json.dumps({"moat_public_score": 86.0}), encoding="utf-8")
            alignment.write_text(json.dumps({"alignment_score": 88.0}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_milestone_public_brief_v1", "--milestone-checkpoint-summary", str(checkpoint), "--moat-public-scoreboard-summary", str(scoreboard), "--snapshot-moat-alignment-summary", str(alignment), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("headline", payload)
            self.assertEqual(payload.get("model_asset_momentum_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
