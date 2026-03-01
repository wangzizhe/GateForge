import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelIntakeBoardHistoryV1Tests(unittest.TestCase):
    def test_history_appends_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(
                json.dumps({"status": "PASS", "board_score": 82.0, "total_candidates": 4, "blocked_count": 1, "ready_count": 2, "ingested_count": 1}),
                encoding="utf-8",
            )
            r2.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "board_score": 74.0, "total_candidates": 4, "blocked_count": 2, "ready_count": 1, "ingested_count": 1}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_intake_board_history_v1",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("total_records", 0)), 2)
            self.assertIsInstance(summary.get("avg_board_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
