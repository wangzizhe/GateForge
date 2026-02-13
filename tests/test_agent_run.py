import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentRunTests(unittest.TestCase):
    def _write_baseline(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-agent-run-1",
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
                    "run_id": "base-agent-run-mismatch-1",
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

    def test_agent_run_demo_mock_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            proposal_out = root / "proposal.json"
            run_out = root / "run.json"
            run_report = root / "run.md"
            candidate_out = root / "candidate.json"
            regression_out = root / "regression.json"
            agent_run_out = root / "agent_run.json"

            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_run",
                    "--intent",
                    "demo_mock_pass",
                    "--proposal-id",
                    "agent-run-test-1",
                    "--proposal-out",
                    str(proposal_out),
                    "--run-out",
                    str(run_out),
                    "--run-report",
                    str(run_report),
                    "--candidate-out",
                    str(candidate_out),
                    "--regression-out",
                    str(regression_out),
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(agent_run_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertTrue(proposal_out.exists())
            self.assertTrue(run_out.exists())
            self.assertTrue(run_report.exists())
            self.assertTrue(candidate_out.exists())
            self.assertTrue(regression_out.exists())
            payload = json.loads(agent_run_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["proposal_id"], "agent-run-test-1")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["run_exit_code"], 0)
            self.assertEqual(payload["policy_version"], "0.1.0")
            self.assertEqual(payload["policy_decision"], "PASS")
            self.assertEqual(payload["fail_reasons"], [])
            self.assertEqual(payload["policy_reasons"], [])
            self.assertIsInstance(payload["human_hints"], list)
            self.assertEqual(payload["change_apply_status"], "not_requested")
            self.assertEqual(payload["change_set_hash"], None)
            self.assertEqual(payload["applied_changes_count"], 0)

    def test_agent_run_demo_mock_fail_exposes_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline_mismatch.json"
            proposal_out = root / "proposal.json"
            run_out = root / "run.json"
            candidate_out = root / "candidate.json"
            regression_out = root / "regression.json"
            agent_run_out = root / "agent_run.json"

            self._write_mismatch_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_run",
                    "--intent",
                    "demo_mock_pass",
                    "--proposal-id",
                    "agent-run-test-fail-1",
                    "--proposal-out",
                    str(proposal_out),
                    "--run-out",
                    str(run_out),
                    "--candidate-out",
                    str(candidate_out),
                    "--regression-out",
                    str(regression_out),
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(agent_run_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(agent_run_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["proposal_id"], "agent-run-test-fail-1")
            self.assertEqual(payload["status"], "FAIL")
            self.assertNotEqual(payload["run_exit_code"], 0)
            self.assertIn("regression_fail", payload["fail_reasons"])
            self.assertEqual(payload["policy_decision"], "FAIL")
            self.assertEqual(payload["change_apply_status"], "not_requested")
            self.assertEqual(payload["change_set_hash"], None)
            self.assertEqual(payload["applied_changes_count"], 0)

    def test_agent_run_from_intent_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            intent_file = root / "intent.json"
            proposal_out = root / "proposal.json"
            run_out = root / "run.json"
            agent_run_out = root / "agent_run.json"

            self._write_baseline(baseline)
            intent_file.write_text(
                json.dumps(
                    {
                        "intent": "demo_mock_pass",
                        "proposal_id": "agent-run-intent-file-1",
                        "overrides": {
                            "risk_level": "medium",
                            "change_summary": "LLM intent file override",
                        },
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_run",
                    "--intent-file",
                    str(intent_file),
                    "--proposal-out",
                    str(proposal_out),
                    "--run-out",
                    str(run_out),
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(agent_run_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            proposal = json.loads(proposal_out.read_text(encoding="utf-8"))
            self.assertEqual(proposal["proposal_id"], "agent-run-intent-file-1")
            self.assertEqual(proposal["risk_level"], "medium")
            self.assertEqual(proposal["change_summary"], "LLM intent file override")
            payload = json.loads(agent_run_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["intent"], "demo_mock_pass")
            self.assertEqual(payload["status"], "PASS")

    def test_agent_run_fails_on_unknown_policy_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            agent_run_out = root / "agent_run.json"
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_run",
                    "--intent",
                    "demo_mock_pass",
                    "--baseline",
                    str(baseline),
                    "--policy-profile",
                    "does_not_exist_profile",
                    "--out",
                    str(agent_run_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
