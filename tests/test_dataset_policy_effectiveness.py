import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyEffectivenessTests(unittest.TestCase):
    def test_keep_when_metrics_improve(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "effectiveness.json"
            before.write_text(
                json.dumps(
                    {
                        "latest_deduplicated_cases": 10,
                        "latest_failure_case_rate": 0.2,
                        "freeze_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    {
                        "latest_deduplicated_cases": 13,
                        "latest_failure_case_rate": 0.27,
                        "freeze_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_effectiveness",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "KEEP")
            self.assertEqual(payload.get("reasons"), [])

    def test_rollback_review_when_freeze_regresses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before = root / "before.json"
            after = root / "after.json"
            out = root / "effectiveness.json"
            before.write_text(
                json.dumps(
                    {
                        "latest_deduplicated_cases": 10,
                        "latest_failure_case_rate": 0.2,
                        "freeze_pass_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            after.write_text(
                json.dumps(
                    {
                        "latest_deduplicated_cases": 11,
                        "latest_failure_case_rate": 0.23,
                        "freeze_pass_rate": 0.8,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_effectiveness",
                    "--before",
                    str(before),
                    "--after",
                    str(after),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "ROLLBACK_REVIEW")
            self.assertIn("freeze_pass_rate_regressed", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()

