import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureMatrixExpansionHistoryTrendV1Tests(unittest.TestCase):
    def test_history_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps({"status": "PASS", "avg_expansion_readiness_score": 81.0, "avg_high_risk_uncovered_cells": 0.0, "avg_planned_expansion_tasks": 6.0}),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "avg_expansion_readiness_score": 75.0, "avg_high_risk_uncovered_cells": 0.5, "avg_planned_expansion_tasks": 7.0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_matrix_expansion_history_trend_v1",
                    "--current",
                    str(current),
                    "--previous",
                    str(previous),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("avg_high_risk_uncovered_cells_increasing", (payload.get("trend") or {}).get("alerts", []))


if __name__ == "__main__":
    unittest.main()
