import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPackExecutionTrackerTests(unittest.TestCase):
    def test_tracker_needs_review_when_large_lagging(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            executed = root / "executed.json"
            out = root / "summary.json"
            plan.write_text(json.dumps({"total_target_new_cases": 10, "scale_plan": [{"scale": "large", "target_new_cases": 3}]}), encoding="utf-8")
            executed.write_text(json.dumps({"completed_cases": 3, "blocked_cases": 0, "scale_completed": {"large": 0}}), encoding="utf-8")
            proc = subprocess.run([
                sys.executable,
                "-m",
                "gateforge.dataset_pack_execution_tracker",
                "--modelica-failure-pack-plan",
                str(plan),
                "--executed-summary",
                str(executed),
                "--out",
                str(out),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("large_scale_progress_low", payload.get("reasons", []))

    def test_tracker_fail_when_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run([
                sys.executable,
                "-m",
                "gateforge.dataset_pack_execution_tracker",
                "--modelica-failure-pack-plan",
                str(root / "missing_plan.json"),
                "--executed-summary",
                str(root / "missing_executed.json"),
                "--out",
                str(out),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
