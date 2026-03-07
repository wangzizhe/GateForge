from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaLiveFocusBoostCompareV0Tests(unittest.TestCase):
    def test_compare_pass_on_regression_and_physics_reduction(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before_summary = root / "before_summary.json"
            before_results = root / "before_results.json"
            after_summary = root / "after_summary.json"
            after_results = root / "after_results.json"
            focus_queue = root / "focus_queue.json"
            focus_templates = root / "focus_templates.json"
            out = root / "out.json"

            before_summary.write_text(
                json.dumps(
                    {
                        "total_tasks": 3,
                        "success_count": 1,
                        "success_at_k_pct": 33.33,
                        "regression_count": 2,
                        "physics_fail_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            before_results.write_text(json.dumps({"records": []}), encoding="utf-8")
            after_summary.write_text(
                json.dumps(
                    {
                        "total_tasks": 3,
                        "success_count": 2,
                        "success_at_k_pct": 66.67,
                        "regression_count": 1,
                        "physics_fail_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            after_results.write_text(json.dumps({"records": []}), encoding="utf-8")
            focus_queue.write_text(
                json.dumps({"queue": [{"rank": 1, "failure_type": "simulate_error", "gate_break_reason": "regression_fail"}]}),
                encoding="utf-8",
            )
            focus_templates.write_text(
                json.dumps({"templates": [{"rank": 1, "failure_type": "simulate_error", "template_id": "tpl_simulate_runtime_guard_v1"}]}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_live_focus_boost_compare_v0",
                    "--before-run-summary",
                    str(before_summary),
                    "--before-run-results",
                    str(before_results),
                    "--after-run-summary",
                    str(after_summary),
                    "--after-run-results",
                    str(after_results),
                    "--focus-queue",
                    str(focus_queue),
                    "--focus-templates",
                    str(focus_templates),
                    "--out",
                    str(out),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("delta", {}).get("regression_count"), -1.0)
            self.assertEqual(payload.get("delta", {}).get("physics_fail_count"), -1.0)

    def test_compare_fail_when_regression_increases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before_summary = root / "before_summary.json"
            before_results = root / "before_results.json"
            after_summary = root / "after_summary.json"
            after_results = root / "after_results.json"
            out = root / "out.json"

            before_summary.write_text(
                json.dumps(
                    {
                        "total_tasks": 3,
                        "success_count": 2,
                        "success_at_k_pct": 66.67,
                        "regression_count": 0,
                        "physics_fail_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            before_results.write_text(json.dumps({"records": []}), encoding="utf-8")
            after_summary.write_text(
                json.dumps(
                    {
                        "total_tasks": 3,
                        "success_count": 2,
                        "success_at_k_pct": 66.67,
                        "regression_count": 1,
                        "physics_fail_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            after_results.write_text(json.dumps({"records": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_live_focus_boost_compare_v0",
                    "--before-run-summary",
                    str(before_summary),
                    "--before-run-results",
                    str(before_results),
                    "--after-run-summary",
                    str(after_summary),
                    "--after-run-results",
                    str(after_results),
                    "--out",
                    str(out),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertIn("regression_count_increased", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
