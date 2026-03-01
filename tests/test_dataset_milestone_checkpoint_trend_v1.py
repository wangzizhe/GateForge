import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMilestoneCheckpointTrendV1Tests(unittest.TestCase):
    def test_checkpoint_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "summary.json"
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "checkpoint_score": 78.0,
                        "milestone_decision": "LIMITED_GO",
                        "model_asset_momentum_status": "NEEDS_REVIEW",
                        "model_asset_momentum_score": 74.0,
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "checkpoint_score": 84.0,
                        "milestone_decision": "GO",
                        "model_asset_momentum_status": "PASS",
                        "model_asset_momentum_score": 82.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_milestone_checkpoint_trend_v1", "--summary", str(current), "--previous-summary", str(previous), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("->", (payload.get("trend") or {}).get("status_transition", ""))
            self.assertIn("->", (payload.get("trend") or {}).get("model_asset_momentum_status_transition", ""))


if __name__ == "__main__":
    unittest.main()
