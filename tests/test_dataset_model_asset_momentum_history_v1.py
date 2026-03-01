import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelAssetMomentumHistoryV1Tests(unittest.TestCase):
    def test_history_appends_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(json.dumps({"status": "PASS", "momentum_score": 82.0, "delta_total_real_models": 2, "delta_large_models": 1}), encoding="utf-8")
            r2.write_text(json.dumps({"status": "PASS", "momentum_score": 79.0, "delta_total_real_models": 1, "delta_large_models": 1}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_momentum_history_v1",
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
            self.assertIsInstance(payload.get("avg_momentum_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
