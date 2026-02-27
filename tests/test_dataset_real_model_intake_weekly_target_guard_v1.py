import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelIntakeWeeklyTargetGuardV1Tests(unittest.TestCase):
    def test_guard_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            out = root / "summary.json"
            intake.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "accepted_count": 4,
                        "accepted_large_count": 1,
                        "reject_rate_pct": 20.0,
                        "weekly_target_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_weekly_target_guard_v1",
                    "--intake-summary",
                    str(intake),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")

    def test_guard_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            out = root / "summary.json"
            intake.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "accepted_count": 2,
                        "accepted_large_count": 0,
                        "reject_rate_pct": 55.0,
                        "weekly_target_status": "NEEDS_REVIEW",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_weekly_target_guard_v1",
                    "--intake-summary",
                    str(intake),
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

    def test_guard_fail_when_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_weekly_target_guard_v1",
                    "--intake-summary",
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
