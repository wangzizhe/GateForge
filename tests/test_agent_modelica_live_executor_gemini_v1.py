import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_live_executor_gemini_v1 import _extract_json_object, _parse_repair_actions


class AgentModelicaLiveExecutorGeminiV1Tests(unittest.TestCase):
    def test_parse_repair_actions_supports_json_and_pipe_formats(self) -> None:
        self.assertEqual(_parse_repair_actions('["a","b"]'), ["a", "b"])
        self.assertEqual(_parse_repair_actions("a | b | c"), ["a", "b", "c"])

    def test_extract_json_object_supports_fenced_payload(self) -> None:
        payload = _extract_json_object("```json\n{\"patched_model_text\":\"model M\\nend M;\"}\n```")
        self.assertEqual(payload.get("patched_model_text"), "model M\nend M;")

    def test_cli_returns_model_path_missing_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_exec_test_") as td:
            out_path = Path(td) / "out.json"
            missing_path = Path(td) / "missing.mo"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_live_executor_gemini_v1",
                    "--task-id",
                    "demo-task",
                    "--mutated-model-path",
                    str(missing_path),
                    "--planner-backend",
                    "rule",
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            stdout_last = proc.stdout.strip().splitlines()[-1]
            payload = json.loads(stdout_last)
            self.assertEqual(payload.get("error_message"), "model_path_missing")
            self.assertFalse(bool(payload.get("check_model_pass")))
            self.assertTrue(out_path.exists())
            out_payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(out_payload.get("task_id"), "demo-task")


if __name__ == "__main__":
    unittest.main()
