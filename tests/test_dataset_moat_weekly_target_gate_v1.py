import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatWeeklyTargetGateV1Tests(unittest.TestCase):
    def test_weekly_target_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            realrun = root / "realrun.json"
            large_auth = root / "large_auth.json"
            out = root / "summary.json"
            intake.write_text(json.dumps({"accepted_count": 6}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 80}), encoding="utf-8")
            large_auth.write_text(json.dumps({"status": "PASS", "large_model_authenticity_score": 74.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_weekly_target_gate_v1",
                    "--intake-runner-summary",
                    str(intake),
                    "--mutation-real-runner-summary",
                    str(realrun),
                    "--large-model-authenticity-summary",
                    str(large_auth),
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
            self.assertEqual(payload.get("weekly_target_status"), "PASS")

    def test_weekly_target_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            realrun = root / "realrun.json"
            large_auth = root / "large_auth.json"
            out = root / "summary.json"
            intake.write_text(json.dumps({"accepted_count": 2}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 6}), encoding="utf-8")
            large_auth.write_text(json.dumps({"status": "NEEDS_REVIEW", "large_model_authenticity_score": 40.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_weekly_target_gate_v1",
                    "--intake-runner-summary",
                    str(intake),
                    "--mutation-real-runner-summary",
                    str(realrun),
                    "--large-model-authenticity-summary",
                    str(large_auth),
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


if __name__ == "__main__":
    unittest.main()
