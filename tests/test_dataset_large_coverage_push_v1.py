import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeCoveragePushV1Tests(unittest.TestCase):
    def test_push_plan_needs_review_when_large_gap_exists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = root / "db.json"
            ladder = root / "ladder.json"
            queue = root / "queue.json"
            out = root / "summary.json"

            db.write_text(
                json.dumps(
                    {
                        "schema_version": "failure_corpus_db_v1",
                        "cases": [
                            {"case_id": "c1", "model_scale": "small", "failure_type": "simulate_error"},
                            {"case_id": "c2", "model_scale": "small", "failure_type": "model_check_error"},
                            {"case_id": "c3", "model_scale": "medium", "failure_type": "semantic_regression"},
                            {"case_id": "c4", "model_scale": "large", "failure_type": "simulate_error"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ladder.write_text(json.dumps({"status": "NEEDS_REVIEW", "large_ready": False}), encoding="utf-8")
            queue.write_text(
                json.dumps(
                    {
                        "queue": [
                            {"queue_id": "q1", "priority": "P0", "reason": "large_model_scale_gap"},
                            {"queue_id": "q2", "priority": "P1", "reason": "distribution_drift"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_coverage_push_v1",
                    "--failure-corpus-db",
                    str(db),
                    "--model-scale-ladder-summary",
                    str(ladder),
                    "--large-model-failure-queue",
                    str(queue),
                    "--target-large-share-pct",
                    "30",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertGreaterEqual(int(summary.get("push_target_large_cases", 0)), 1)
            self.assertIn("large_failure_type_coverage_gaps", summary.get("alerts", []))

    def test_push_plan_passes_when_large_coverage_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = root / "db.json"
            ladder = root / "ladder.json"
            out = root / "summary.json"

            db.write_text(
                json.dumps(
                    {
                        "schema_version": "failure_corpus_db_v1",
                        "cases": [
                            {"case_id": "c1", "model_scale": "large", "failure_type": "simulate_error"},
                            {"case_id": "c2", "model_scale": "large", "failure_type": "model_check_error"},
                            {"case_id": "c3", "model_scale": "large", "failure_type": "semantic_regression"},
                            {"case_id": "c4", "model_scale": "large", "failure_type": "numerical_instability"},
                            {"case_id": "c5", "model_scale": "large", "failure_type": "constraint_violation"},
                            {"case_id": "c6", "model_scale": "medium", "failure_type": "simulate_error"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ladder.write_text(json.dumps({"status": "PASS", "large_ready": True}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_coverage_push_v1",
                    "--failure-corpus-db",
                    str(db),
                    "--model-scale-ladder-summary",
                    str(ladder),
                    "--target-large-share-pct",
                    "60",
                    "--min-new-large-cases",
                    "0",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("push_target_large_cases", 0)), 0)

    def test_push_plan_fails_when_required_sources_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_coverage_push_v1",
                    "--failure-corpus-db",
                    str(root / "missing_db.json"),
                    "--model-scale-ladder-summary",
                    str(root / "missing_ladder.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
