import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_live_executor_gemini_v1 import (
    _bootstrap_env_from_repo,
    _extract_json_object,
    _parse_env_assignment,
    _parse_repair_actions,
)


class AgentModelicaLiveExecutorGeminiV1Tests(unittest.TestCase):
    def test_parse_env_assignment_supports_export_and_quotes(self) -> None:
        self.assertEqual(_parse_env_assignment("export GOOGLE_API_KEY=abc"), ("GOOGLE_API_KEY", "abc"))
        self.assertEqual(_parse_env_assignment('GOOGLE_API_KEY="abc-123"'), ("GOOGLE_API_KEY", "abc-123"))
        self.assertEqual(_parse_env_assignment("# comment"), (None, None))

    def test_bootstrap_env_from_repo_loads_google_api_key_from_cwd_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_env_bootstrap_") as td:
            env_path = Path(td) / ".env"
            env_path.write_text("GOOGLE_API_KEY=test-key\nIGNORED_KEY=1\n", encoding="utf-8")
            prev = os.environ.pop("GOOGLE_API_KEY", None)
            prev_cwd = os.getcwd()
            try:
                os.chdir(td)
                loaded = _bootstrap_env_from_repo(allowed_keys={"GOOGLE_API_KEY"})
                self.assertGreaterEqual(loaded, 1)
                self.assertEqual(os.getenv("GOOGLE_API_KEY"), "test-key")
            finally:
                os.chdir(prev_cwd)
                if prev is None:
                    os.environ.pop("GOOGLE_API_KEY", None)
                else:
                    os.environ["GOOGLE_API_KEY"] = prev

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
