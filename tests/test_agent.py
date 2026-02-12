import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.proposal import validate_proposal


class AgentTests(unittest.TestCase):
    def test_agent_cli_generates_valid_demo_mock_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "agent_proposal.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent",
                    "--intent",
                    "demo_mock_pass",
                    "--proposal-id",
                    "agent-test-1",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            validate_proposal(payload)
            self.assertEqual(payload["author_type"], "agent")
            self.assertEqual(payload["proposal_id"], "agent-test-1")
            self.assertEqual(payload["backend"], "mock")

    def test_agent_cli_runtime_intents_set_expected_risk(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            low = Path(d) / "low.json"
            high = Path(d) / "high.json"
            proc_low = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent",
                    "--intent",
                    "runtime_regress_low_risk",
                    "--out",
                    str(low),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            proc_high = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent",
                    "--intent",
                    "runtime_regress_high_risk",
                    "--out",
                    str(high),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc_low.returncode, 0, msg=proc_low.stderr or proc_low.stdout)
            self.assertEqual(proc_high.returncode, 0, msg=proc_high.stderr or proc_high.stdout)
            low_payload = json.loads(low.read_text(encoding="utf-8"))
            high_payload = json.loads(high.read_text(encoding="utf-8"))
            self.assertEqual(low_payload["risk_level"], "low")
            self.assertEqual(high_payload["risk_level"], "high")

    def test_agent_cli_medium_openmodelica_intent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "medium.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent",
                    "--intent",
                    "medium_openmodelica_pass",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            validate_proposal(payload)
            self.assertEqual(payload["backend"], "openmodelica_docker")
            self.assertEqual(payload["model_script"], "examples/openmodelica/medium_probe.mos")
            self.assertEqual(payload["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
