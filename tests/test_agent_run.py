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


if __name__ == "__main__":
    unittest.main()
