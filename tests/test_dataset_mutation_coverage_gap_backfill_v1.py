import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationCoverageGapBackfillV1Tests(unittest.TestCase):
    def test_backfill_generates_gap_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            matrix = root / "matrix.json"
            summary = root / "summary_input.json"
            guard = root / "guard.json"
            tasks = root / "tasks.json"
            out = root / "summary.json"

            matrix.write_text(
                json.dumps(
                    {
                        "type_confusion": {
                            "medium": [
                                {"expected": "simulate_error", "observed": "simulate_error", "count": 3},
                                {"expected": "simulate_error", "observed": "semantic_regression", "count": 2},
                            ],
                            "large": [
                                {"expected": "model_check_error", "observed": "simulate_error", "count": 4},
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )
            summary.write_text(
                json.dumps({"status": "PASS", "matrix_path": str(matrix)}),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "alerts": ["top1_failure_type_share_high"]}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_coverage_gap_backfill_v1",
                    "--validation-matrix-v2-summary",
                    str(summary),
                    "--failure-distribution-stability-guard-summary",
                    str(guard),
                    "--tasks-out",
                    str(tasks),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            task_payload = json.loads(tasks.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertGreaterEqual(int(payload.get("total_tasks", 0)), 1)
            self.assertGreaterEqual(len(task_payload.get("tasks") or []), 1)

    def test_backfill_fail_when_summary_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_coverage_gap_backfill_v1",
                    "--validation-matrix-v2-summary",
                    str(root / "missing_summary.json"),
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
