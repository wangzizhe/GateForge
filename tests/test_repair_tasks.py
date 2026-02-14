import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairTasksTests(unittest.TestCase):
    def test_generate_tasks_from_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            out = root / "tasks.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "repair-tasks-001",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "risk_level": "medium",
                        "policy_reasons": ["runtime_regression:1.2s>1.0s"],
                        "fail_reasons": ["regression_fail"],
                        "candidate_path": "artifacts/candidate.json",
                        "regression_path": "artifacts/regression.json",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_tasks",
                    "--source",
                    str(source),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("proposal_id"), "repair-tasks-001")
            self.assertEqual(payload.get("policy_decision"), "FAIL")
            self.assertGreaterEqual(payload.get("task_count", 0), 4)
            self.assertIn("priority_counts", payload)
            self.assertIn("group_counts", payload)
            self.assertGreaterEqual(payload.get("priority_counts", {}).get("P0", 0), 1)
            self.assertTrue(payload.get("tasks_by_priority", {}).get("P0", []))

    def test_generate_tasks_from_regression_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "regression.json"
            out = root / "tasks.json"
            source.write_text(
                json.dumps(
                    {
                        "decision": "FAIL",
                        "reasons": ["runtime_regression:1.2s>1.0s"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_tasks",
                    "--source",
                    str(source),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("source_kind"), "regression")
            self.assertIn("runtime_regression:1.2s>1.0s", payload.get("policy_reasons", []))

    def test_generate_tasks_from_autopilot_summary_uses_run_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = root / "run_summary.json"
            source = root / "autopilot_summary.json"
            out = root / "tasks.json"
            run.write_text(
                json.dumps(
                    {
                        "proposal_id": "repair-tasks-002",
                        "status": "NEEDS_REVIEW",
                        "policy_decision": "NEEDS_REVIEW",
                        "risk_level": "high",
                        "policy_reasons": ["change_plan_confidence_below_auto_apply"],
                        "fail_reasons": [],
                    }
                ),
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "repair-tasks-002",
                        "run_path": str(run),
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_tasks",
                    "--source",
                    str(source),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("proposal_id"), "repair-tasks-002")
            self.assertEqual(payload.get("policy_decision"), "NEEDS_REVIEW")
            self.assertTrue(payload.get("tasks"))


if __name__ == "__main__":
    unittest.main()
