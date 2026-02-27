import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetIntakeGrowthExecutionBoardV1Tests(unittest.TestCase):
    def test_board_builds_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            intake = root / "intake.json"
            matrix = root / "matrix.json"
            bmk = root / "bmk.json"
            out = root / "summary.json"
            advisor.write_text(json.dumps({"status": "NEEDS_REVIEW", "advice": {"backlog_actions": [{"task_id": "t1", "priority": "P0"}]}}), encoding="utf-8")
            intake.write_text(json.dumps({"accepted_count": 2, "accepted_large_count": 0, "reject_rate_pct": 40.0}), encoding="utf-8")
            matrix.write_text(json.dumps({"matrix_execution_ratio_pct": 80.0}), encoding="utf-8")
            bmk.write_text(json.dumps({"failure_type_drift": 0.14}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_execution_board_v1",
                    "--intake-growth-advisor-summary",
                    str(advisor),
                    "--real-model-intake-summary",
                    str(intake),
                    "--mutation-execution-matrix-summary",
                    str(matrix),
                    "--failure-distribution-benchmark-v2-summary",
                    str(bmk),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(payload.get("task_count", 0)), 1)

    def test_board_fail_when_missing_advisor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_execution_board_v1",
                    "--intake-growth-advisor-summary",
                    str(root / "missing.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
