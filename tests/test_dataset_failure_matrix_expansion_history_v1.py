import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureMatrixExpansionHistoryV1Tests(unittest.TestCase):
    def test_history_appends_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(
                json.dumps({"status": "PASS", "expansion_readiness_score": 82.0, "high_risk_uncovered_cells": 0, "planned_expansion_tasks": 6}),
                encoding="utf-8",
            )
            r2.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "expansion_readiness_score": 74.0, "high_risk_uncovered_cells": 1, "planned_expansion_tasks": 7}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_matrix_expansion_history_v1",
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
            self.assertIsInstance(summary.get("avg_expansion_readiness_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
