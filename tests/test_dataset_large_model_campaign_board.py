import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelCampaignBoardTests(unittest.TestCase):
    def test_board_outputs_phase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            q = root / "q.json"
            t = root / "t.json"
            f = root / "f.json"
            out = root / "out.json"
            q.write_text(json.dumps({"total_queue_items": 4}), encoding="utf-8")
            t.write_text(json.dumps({"large_scale_progress_percent": 50.0}), encoding="utf-8")
            f.write_text(json.dumps({"projected_moat_score_30d": 72.0}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_large_model_campaign_board", "--large-model-failure-queue", str(q), "--pack-execution-tracker", str(t), "--moat-execution-forecast", str(f), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("campaign_phase"), {"stabilize", "scale_out", "accelerate"})

    def test_board_fail_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_large_model_campaign_board", "--large-model-failure-queue", str(Path(d) / "missing1.json"), "--pack-execution-tracker", str(Path(d) / "missing2.json"), "--moat-execution-forecast", str(Path(d) / "missing3.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
