import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_live_executor_mock_v0 import build_payload


class AgentModelicaLiveExecutorMockV0Tests(unittest.TestCase):
    def test_build_payload_keeps_failure_type_and_stage(self) -> None:
        payload = build_payload(
            task_id="t1",
            failure_type="simulate_error",
            expected_stage="simulate",
        )
        self.assertEqual(payload.get("task_id"), "t1")
        self.assertEqual(payload.get("executor_status"), "PASS")
        self.assertTrue(payload.get("check_model_pass"))
        attempts = payload.get("attempts") if isinstance(payload.get("attempts"), list) else []
        self.assertEqual(len(attempts), 1)
        attempt = attempts[0] if isinstance(attempts[0], dict) else {}
        self.assertEqual(attempt.get("round"), 1)
        self.assertTrue(attempt.get("check_model_pass"))
        self.assertTrue(attempt.get("simulate_pass"))
        self.assertEqual(attempt.get("observed_failure_type"), "simulate_error")
        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        self.assertEqual(diagnostic.get("error_type"), "simulate_error")
        self.assertEqual(diagnostic.get("stage"), "simulate")

    def test_module_can_write_payload_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "payload.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_live_executor_mock_v0",
                    "--task-id",
                    "t2",
                    "--failure-type",
                    "model_check_error",
                    "--expected-stage",
                    "check",
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            stdout_payload = json.loads(proc.stdout)
            file_payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(stdout_payload, file_payload)
            self.assertEqual(stdout_payload.get("task_id"), "t2")
            self.assertEqual(stdout_payload.get("backend_used"), "mock")


if __name__ == "__main__":
    unittest.main()
