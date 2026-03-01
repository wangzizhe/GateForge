import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelAssetTargetGapHistoryV1Tests(unittest.TestCase):
    def test_history_appends_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(json.dumps({"status": "NEEDS_REVIEW", "target_gap_score": 28.5, "critical_gap_count": 1}), encoding="utf-8")
            r2.write_text(json.dumps({"status": "PASS", "target_gap_score": 20.0, "critical_gap_count": 0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_target_gap_history_v1",
                    "--record",
                    str(r1),
                    "--record",
                    str(r2),
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("total_records", 0)), 2)
            self.assertIsInstance(payload.get("avg_target_gap_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
