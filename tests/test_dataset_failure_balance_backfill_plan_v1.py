import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureBalanceBackfillPlanV1Tests(unittest.TestCase):
    def test_backfill_plan_generates_actions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            guard = root / "guard.json"
            out = root / "summary.json"
            guard.write_text(
                json.dumps(
                    {
                        "expected_distribution": {
                            "simulate_error": 60,
                            "model_check_error": 10,
                            "semantic_regression": 10,
                            "numerical_instability": 10,
                            "constraint_violation": 10,
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_balance_backfill_plan_v1",
                    "--mutation-failure-type-balance-guard-summary",
                    str(guard),
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
            self.assertGreaterEqual(int(payload.get("total_actions", 0)), 1)

    def test_backfill_plan_fail_when_missing_guard(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_balance_backfill_plan_v1",
                    "--mutation-failure-type-balance-guard-summary",
                    str(root / "missing_guard.json"),
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
