import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetIntakeGrowthAdvisorV1Tests(unittest.TestCase):
    def test_advisor_needs_review_with_growth_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            guard = root / "guard.json"
            matrix = root / "matrix.json"
            bmk = root / "bmk.json"
            out = root / "summary.json"

            intake.write_text(json.dumps({"status": "NEEDS_REVIEW", "accepted_count": 2, "accepted_large_count": 0, "reject_rate_pct": 50.0, "weekly_target_status": "NEEDS_REVIEW"}), encoding="utf-8")
            guard.write_text(json.dumps({"status": "NEEDS_REVIEW"}), encoding="utf-8")
            matrix.write_text(json.dumps({"matrix_execution_ratio_pct": 80.0, "missing_cells": [{"model_scale": "large", "failure_type": "simulate_error", "missing_mutations": 2}]}), encoding="utf-8")
            bmk.write_text(json.dumps({"failure_type_drift": 0.16}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_advisor_v1",
                    "--real-model-intake-summary",
                    str(intake),
                    "--real-model-intake-weekly-target-guard-summary",
                    str(guard),
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
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertGreaterEqual(len(((payload.get("advice") or {}).get("backlog_actions") or [])), 1)

    def test_advisor_fail_when_missing_intake(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_intake_growth_advisor_v1",
                    "--real-model-intake-summary",
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
