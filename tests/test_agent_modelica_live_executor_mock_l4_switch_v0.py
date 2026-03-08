import json
import subprocess
import sys
import unittest


class AgentModelicaLiveExecutorMockL4SwitchV0Tests(unittest.TestCase):
    def _run(self, enabled: str) -> dict:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_live_executor_mock_l4_switch_v0",
                "--task-id",
                "t1",
                "--l4-enabled",
                enabled,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        return json.loads(proc.stdout.strip())

    def test_returns_pass_when_l4_enabled(self) -> None:
        payload = self._run("1")
        self.assertTrue(bool(payload.get("check_model_pass")))
        self.assertTrue(bool(payload.get("simulate_pass")))
        self.assertEqual(str(payload.get("executor_status") or ""), "PASS")

    def test_returns_fail_when_l4_disabled(self) -> None:
        payload = self._run("0")
        self.assertFalse(bool(payload.get("check_model_pass")))
        self.assertFalse(bool(payload.get("simulate_pass")))
        self.assertEqual(str(payload.get("executor_status") or ""), "FAILED")


if __name__ == "__main__":
    unittest.main()
