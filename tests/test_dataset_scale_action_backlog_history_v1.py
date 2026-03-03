import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleActionBacklogHistoryV1Tests(unittest.TestCase):
    def test_backlog_history_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            board = root / "board.json"
            family = root / "family.json"
            failure = root / "failure.json"
            checkpoint = root / "checkpoint.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            board.write_text(json.dumps({"status": "NEEDS_REVIEW", "p0_tasks": 2, "task_count": 5}), encoding="utf-8")
            family.write_text(json.dumps({"status": "NEEDS_REVIEW", "p0_actions": 1, "total_actions": 2}), encoding="utf-8")
            failure.write_text(json.dumps({"status": "PASS", "p0_actions": 0, "total_actions": 1}), encoding="utf-8")
            checkpoint.write_text(json.dumps({"status": "NEEDS_REVIEW", "milestone_score": 71.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_action_backlog_history_v1",
                    "--scale-execution-priority-board-summary",
                    str(board),
                    "--family-gap-action-plan-summary",
                    str(family),
                    "--failure-balance-backfill-plan-summary",
                    str(failure),
                    "--weekly-scale-milestone-checkpoint-summary",
                    str(checkpoint),
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
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(payload.get("total_records", 0)), 1)

    def test_backlog_history_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_action_backlog_history_v1",
                    "--scale-execution-priority-board-summary",
                    str(root / "missing_board.json"),
                    "--family-gap-action-plan-summary",
                    str(root / "missing_family.json"),
                    "--failure-balance-backfill-plan-summary",
                    str(root / "missing_failure.json"),
                    "--weekly-scale-milestone-checkpoint-summary",
                    str(root / "missing_checkpoint.json"),
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
