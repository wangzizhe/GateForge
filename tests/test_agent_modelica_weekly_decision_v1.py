import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaWeeklyDecisionV1Tests(unittest.TestCase):
    def test_promote_when_improved_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            out = root / "decision.json"
            current.write_text(
                json.dumps(
                    {
                        "week_tag": "2026-W10",
                        "baseline_status": "PASS",
                        "regression_count": 0,
                        "physics_fail_count": 0,
                        "delta_vs_previous": {
                            "success_at_k_pct": 5.0,
                            "median_time_to_pass_sec": -10.0,
                            "median_repair_rounds": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_weekly_decision_v1",
                    "--current-page",
                    str(current),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "PROMOTE")

    def test_rollback_when_safety_violated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            out = root / "decision.json"
            current.write_text(
                json.dumps(
                    {
                        "week_tag": "2026-W10",
                        "baseline_status": "PASS",
                        "regression_count": 1,
                        "physics_fail_count": 0,
                        "delta_vs_previous": {
                            "success_at_k_pct": 0.0,
                            "median_time_to_pass_sec": 0.0,
                            "median_repair_rounds": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_weekly_decision_v1",
                    "--current-page",
                    str(current),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "ROLLBACK")

    def test_thresholds_can_force_hold_on_tiny_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            out = root / "decision.json"
            current.write_text(
                json.dumps(
                    {
                        "week_tag": "2026-W10",
                        "baseline_status": "PASS",
                        "regression_count": 0,
                        "physics_fail_count": 0,
                        "delta_vs_previous": {
                            "success_at_k_pct": 0.02,
                            "median_time_to_pass_sec": 0.0,
                            "median_repair_rounds": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_weekly_decision_v1",
                    "--current-page",
                    str(current),
                    "--min-success-delta-promote",
                    "0.05",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "HOLD")


if __name__ == "__main__":
    unittest.main()
