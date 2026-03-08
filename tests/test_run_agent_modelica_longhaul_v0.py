import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


def _cmd_pass_with_artifact() -> str:
    code = """
import os
from pathlib import Path
out_dir = Path(os.environ.get("GATEFORGE_AGENT_LONGHAUL_SEGMENT_OUT_DIR", "."))
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "ok.txt").write_text("ok", encoding="utf-8")
print("segment-pass")
""".strip()
    return f"python3 -c {shlex.quote(code)}"


def _cmd_fail() -> str:
    code = "import sys; sys.exit(2)"
    return f"python3 -c {shlex.quote(code)}"


class RunAgentModelicaLonghaulV0ScriptTests(unittest.TestCase):
    def test_longhaul_runs_multiple_segments(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_longhaul_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            env = {
                **os.environ,
                "GATEFORGE_AGENT_LONGHAUL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_LONGHAUL_TOTAL_MINUTES": "120",
                "GATEFORGE_AGENT_LONGHAUL_SEGMENT_TIMEOUT_SEC": "10",
                "GATEFORGE_AGENT_LONGHAUL_MAX_SEGMENTS": "2",
                "GATEFORGE_AGENT_LONGHAUL_RETRY_PER_SEGMENT": "0",
                "GATEFORGE_AGENT_LONGHAUL_CONTINUE_ON_FAIL": "0",
                "GATEFORGE_AGENT_LONGHAUL_SLEEP_BETWEEN_SEC": "0",
                "GATEFORGE_AGENT_LONGHAUL_SEGMENT_COMMAND": _cmd_pass_with_artifact(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "PASS")
            self.assertEqual(int(summary.get("segments_total") or -1), 2)
            self.assertEqual(int(summary.get("segments_completed") or -1), 2)
            self.assertEqual(int(summary.get("segments_failed", -1)), 0)
            self.assertEqual(str(summary.get("stop_reason") or ""), "max_segments_reached")
            self.assertTrue((out_dir / "runs" / "segment_0001" / "ok.txt").exists())
            self.assertTrue((out_dir / "runs" / "segment_0002" / "ok.txt").exists())

    def test_longhaul_resume_continues_from_state(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_longhaul_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out_resume"
            env1 = {
                **os.environ,
                "GATEFORGE_AGENT_LONGHAUL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_LONGHAUL_TOTAL_MINUTES": "120",
                "GATEFORGE_AGENT_LONGHAUL_SEGMENT_TIMEOUT_SEC": "10",
                "GATEFORGE_AGENT_LONGHAUL_MAX_SEGMENTS": "1",
                "GATEFORGE_AGENT_LONGHAUL_RETRY_PER_SEGMENT": "0",
                "GATEFORGE_AGENT_LONGHAUL_CONTINUE_ON_FAIL": "0",
                "GATEFORGE_AGENT_LONGHAUL_SLEEP_BETWEEN_SEC": "0",
                "GATEFORGE_AGENT_LONGHAUL_SEGMENT_COMMAND": _cmd_pass_with_artifact(),
            }
            first = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                env=env1,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(first.returncode, 0, msg=first.stderr or first.stdout)

            env2 = {
                **env1,
                "GATEFORGE_AGENT_LONGHAUL_MAX_SEGMENTS": "2",
                "GATEFORGE_AGENT_LONGHAUL_RESUME": "1",
            }
            second = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                env=env2,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(second.returncode, 0, msg=second.stderr or second.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("segments_total") or -1), 2)
            self.assertEqual(int(summary.get("segments_completed") or -1), 2)
            state = json.loads((out_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(int(state.get("next_segment_index") or -1), 3)

    def test_longhaul_fails_fast_when_continue_on_fail_disabled(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_longhaul_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out_fail"
            env = {
                **os.environ,
                "GATEFORGE_AGENT_LONGHAUL_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_LONGHAUL_TOTAL_MINUTES": "120",
                "GATEFORGE_AGENT_LONGHAUL_SEGMENT_TIMEOUT_SEC": "10",
                "GATEFORGE_AGENT_LONGHAUL_MAX_SEGMENTS": "2",
                "GATEFORGE_AGENT_LONGHAUL_RETRY_PER_SEGMENT": "0",
                "GATEFORGE_AGENT_LONGHAUL_CONTINUE_ON_FAIL": "0",
                "GATEFORGE_AGENT_LONGHAUL_SLEEP_BETWEEN_SEC": "0",
                "GATEFORGE_AGENT_LONGHAUL_SEGMENT_COMMAND": _cmd_fail(),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "FAIL")
            self.assertEqual(str(summary.get("stop_reason") or ""), "segment_failed")
            self.assertEqual(int(summary.get("segments_total") or -1), 1)


if __name__ == "__main__":
    unittest.main()
