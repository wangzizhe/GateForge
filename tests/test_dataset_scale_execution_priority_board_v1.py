import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleExecutionPriorityBoardV1Tests(unittest.TestCase):
    def test_priority_board_builds_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gap = root / "gap.json"
            planner = root / "planner.json"
            hard = root / "hard.json"
            backfill = root / "backfill.json"
            out = root / "summary.json"

            gap.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "gap_models": 200,
                        "gap_reproducible_mutations": 5000,
                        "gap_hardness_score": 8.0,
                        "required_weekly_new_models": 20,
                        "required_weekly_new_reproducible_mutations": 420,
                    }
                ),
                encoding="utf-8",
            )
            planner.write_text(json.dumps({"p0_channels": 2}), encoding="utf-8")
            hard.write_text(json.dumps({"failed_gate_count": 3}), encoding="utf-8")
            backfill.write_text(json.dumps({"p0_tasks": 2}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_execution_priority_board_v1",
                    "--scale-target-gap-summary",
                    str(gap),
                    "--ingest-source-channel-planner-summary",
                    str(planner),
                    "--hard-moat-gates-summary",
                    str(hard),
                    "--coverage-backfill-summary",
                    str(backfill),
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
            self.assertGreaterEqual(int(payload.get("task_count", 0)), 3)
            self.assertGreaterEqual(int(payload.get("p0_tasks", 0)), 1)

    def test_priority_board_fail_when_gap_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_execution_priority_board_v1",
                    "--scale-target-gap-summary",
                    str(root / "missing_gap.json"),
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
