import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AutopilotTests(unittest.TestCase):
    def _write_baseline(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-autopilot-1",
                    "backend": "mock",
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "status": "success",
                    "gate": "PASS",
                    "check_ok": True,
                    "simulate_ok": True,
                    "metrics": {"runtime_seconds": 0.1},
                }
            ),
            encoding="utf-8",
        )

    def _write_mismatch_baseline(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-autopilot-mismatch-1",
                    "backend": "openmodelica_docker",
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "status": "success",
                    "gate": "PASS",
                    "check_ok": True,
                    "simulate_ok": True,
                    "metrics": {"runtime_seconds": 0.1},
                }
            ),
            encoding="utf-8",
        )

    def test_autopilot_goal_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            intent_out = root / "intent.json"
            agent_run_out = root / "agent_run.json"
            out = root / "summary.json"
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-1",
                    "--baseline",
                    str(baseline),
                    "--intent-out",
                    str(intent_out),
                    "--agent-run-out",
                    str(agent_run_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["proposal_id"], "autopilot-test-1")
            self.assertEqual(payload["intent"], "demo_mock_pass")
            self.assertEqual(payload["planner_exit_code"], 0)
            self.assertEqual(payload["agent_run_exit_code"], 0)

    def test_autopilot_context_json_propagates_to_intent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            intent_out = root / "intent.json"
            agent_run_out = root / "agent_run.json"
            out = root / "summary.json"
            context = root / "context.json"
            self._write_baseline(baseline)
            context.write_text(
                json.dumps(
                    {
                        "risk_level": "medium",
                        "change_summary": "context override in autopilot",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-2",
                    "--baseline",
                    str(baseline),
                    "--context-json",
                    str(context),
                    "--intent-out",
                    str(intent_out),
                    "--agent-run-out",
                    str(agent_run_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            intent_payload = json.loads(intent_out.read_text(encoding="utf-8"))
            self.assertEqual(intent_payload["overrides"]["risk_level"], "medium")
            self.assertEqual(intent_payload["overrides"]["change_summary"], "context override in autopilot")

    def test_autopilot_fail_on_baseline_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline_mismatch.json"
            out = root / "summary.json"
            self._write_mismatch_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.autopilot",
                    "--goal",
                    "run demo mock pass",
                    "--proposal-id",
                    "autopilot-test-fail-1",
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "FAIL")
            self.assertEqual(payload["policy_decision"], "FAIL")
            self.assertTrue(payload["fail_reasons"])


if __name__ == "__main__":
    unittest.main()
