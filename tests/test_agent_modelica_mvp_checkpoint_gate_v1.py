import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaMvpCheckpointGateV1Tests(unittest.TestCase):
    def test_go_when_daily_ab_holdout_all_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            daily = root / "daily.json"
            ab = root / "ab.json"
            holdout = root / "holdout.json"
            out = root / "decision.json"

            daily.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "success_at_k_pct": 100.0,
                        "regression_count": 0,
                        "physics_fail_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            ab.write_text(
                json.dumps({"delta_on_minus_off": {"success_at_k_pct": 20.0, "regression_count": -3.0}}),
                encoding="utf-8",
            )
            holdout.write_text(
                json.dumps({"status": "PASS", "success_at_k_pct": 95.0, "regression_count": 0, "physics_fail_count": 0}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mvp_checkpoint_gate_v1",
                    "--daily-summary",
                    str(daily),
                    "--retrieval-ab-summary",
                    str(ab),
                    "--holdout-summary",
                    str(holdout),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "GO")
            self.assertEqual(payload.get("status"), "PASS")

    def test_stop_when_daily_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            daily = root / "daily.json"
            out = root / "decision.json"
            daily.write_text(json.dumps({"status": "FAIL", "success_at_k_pct": 70.0, "regression_count": 5}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mvp_checkpoint_gate_v1",
                    "--daily-summary",
                    str(daily),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "STOP")
            self.assertIn("daily_fail", payload.get("reasons", []))

    def test_hold_when_holdout_regression_exceeds_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            daily = root / "daily.json"
            holdout = root / "holdout.json"
            out = root / "decision.json"
            daily.write_text(json.dumps({"status": "PASS", "success_at_k_pct": 100.0, "regression_count": 0}), encoding="utf-8")
            holdout.write_text(
                json.dumps({"status": "PASS", "success_at_k_pct": 90.0, "regression_count": 3, "physics_fail_count": 0}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mvp_checkpoint_gate_v1",
                    "--daily-summary",
                    str(daily),
                    "--holdout-summary",
                    str(holdout),
                    "--max-holdout-regression-count",
                    "1",
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
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("holdout_regression_above_threshold", payload.get("reasons", []))

    def test_hold_when_focus_hit_rate_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            daily = root / "daily.json"
            out = root / "decision.json"
            daily.write_text(json.dumps({"status": "PASS", "success_at_k_pct": 100.0, "regression_count": 0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_mvp_checkpoint_gate_v1",
                    "--daily-summary",
                    str(daily),
                    "--daily-focus-hit-rate-pct",
                    "10.0",
                    "--min-daily-focus-hit-rate-pct",
                    "40.0",
                    "--max-daily-focus-miss-rate-pct",
                    "60.0",
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
            self.assertIn("daily_focus_hit_below_threshold", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
