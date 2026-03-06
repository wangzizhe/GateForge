import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_live_executor_gemini_v1 import (
    _apply_parse_error_pre_repair,
    _bootstrap_env_from_repo,
    _extract_json_object,
    _normalize_terminal_errors,
    _parse_env_assignment,
    _parse_repair_actions,
)


class AgentModelicaLiveExecutorGeminiV1Tests(unittest.TestCase):
    def test_normalize_terminal_errors_clears_errors_for_pass(self) -> None:
        err, comp, sim = _normalize_terminal_errors("PASS", "x", "y", "z")
        self.assertEqual((err, comp, sim), ("", "", ""))

    def test_normalize_terminal_errors_keeps_errors_for_failed(self) -> None:
        err, comp, sim = _normalize_terminal_errors("FAILED", "x", "y", "z")
        self.assertEqual((err, comp, sim), ("x", "y", "z"))

    def test_apply_parse_error_pre_repair_removes_injected_state_tokens(self) -> None:
        model_text = "model A1\n  Real x;\nequation\n  der(x) = -x + __gf_state_301500;\nend A1;\n"
        output = (
            '[/workspace/A1.mo:6:8-6:24:writable] Error: No viable alternative near token: __gf_state_301500'
        )
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "script_parse_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertNotIn("__gf_state_301500", patched)
        self.assertIn(
            str(audit.get("reason") or ""),
            {"removed_lines_with_injected_state_tokens", "removed_injected_state_tokens_inline"},
        )

    def test_apply_parse_error_pre_repair_prefers_line_removal_for_injected_block(self) -> None:
        model_text = (
            "model A1\n"
            "  Real x;\n"
            "equation\n"
            "  der(x) = -x;\n"
            "  Real __gf_state_301500(start=1.0);\n"
            "  der(__gf_state_301500) = -1.0 * __gf_state_301500;\n"
            "end A1;\n"
        )
        output = "Error: No viable alternative near token: __gf_state_301500"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "script_parse_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "removed_lines_with_injected_state_tokens")
        self.assertGreaterEqual(int(audit.get("removed_line_count") or 0), 1)
        self.assertNotIn("__gf_state_301500", patched)

    def test_apply_parse_error_pre_repair_noop_for_non_parse_failure_type(self) -> None:
        model_text = "model A1\nend A1;\n"
        output = "Error: Something else"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "simulate_error")
        self.assertEqual(patched, model_text)
        self.assertFalse(bool(audit.get("applied")))

    def test_apply_parse_error_pre_repair_removes_model_check_undef_token_lines(self) -> None:
        model_text = (
            "model A1\n"
            "  Real x;\n"
            "equation\n"
            "  der(x) = -x;\n"
            "  __gf_undef_301300 = 1.0;\n"
            "end A1;\n"
        )
        output = "Error: Variable __gf_undef_301300 not found in scope A1"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "model_check_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "removed_lines_with_injected_undef_tokens")
        self.assertNotIn("__gf_undef_301300", patched)

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
