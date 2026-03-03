import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetWeeklyScaleMilestoneCheckpointV1Tests(unittest.TestCase):
    def test_checkpoint_builds_top_actions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            batch = root / "batch.json"
            gap = root / "gap.json"
            evidence = root / "evidence.json"
            family = root / "family.json"
            failure = root / "failure.json"
            board = root / "board.json"
            out = root / "summary.json"
            batch.write_text(json.dumps({"hard_moat_gates_status": "PASS", "hard_moat_hardness_score": 80.0}), encoding="utf-8")
            gap.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "overall_progress_pct": 55.0,
                        "gap_models": 100,
                        "gap_reproducible_mutations": 500,
                        "required_weekly_new_models": 10,
                        "required_weekly_new_reproducible_mutations": 50,
                    }
                ),
                encoding="utf-8",
            )
            evidence.write_text(json.dumps({"status": "PASS", "evidence_score": 82.0}), encoding="utf-8")
            family.write_text(json.dumps({"status": "PASS", "family_entropy": 1.9, "alerts": []}), encoding="utf-8")
            failure.write_text(json.dumps({"status": "PASS", "expected_entropy": 2.0, "alerts": []}), encoding="utf-8")
            board.write_text(json.dumps({"status": "NEEDS_REVIEW", "p0_tasks": 2}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_weekly_scale_milestone_checkpoint_v1",
                    "--scale-batch-summary",
                    str(batch),
                    "--scale-target-gap-summary",
                    str(gap),
                    "--scale-evidence-stamp-summary",
                    str(evidence),
                    "--real-model-family-coverage-board-summary",
                    str(family),
                    "--mutation-failure-type-balance-guard-summary",
                    str(failure),
                    "--scale-execution-priority-board-summary",
                    str(board),
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
            self.assertGreaterEqual(int(payload.get("top_actions_count", 0)), 1)

    def test_checkpoint_fail_when_required_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_weekly_scale_milestone_checkpoint_v1",
                    "--scale-batch-summary",
                    str(root / "missing_batch.json"),
                    "--scale-target-gap-summary",
                    str(root / "missing_gap.json"),
                    "--scale-evidence-stamp-summary",
                    str(root / "missing_evidence.json"),
                    "--real-model-family-coverage-board-summary",
                    str(root / "missing_family.json"),
                    "--mutation-failure-type-balance-guard-summary",
                    str(root / "missing_failure.json"),
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
