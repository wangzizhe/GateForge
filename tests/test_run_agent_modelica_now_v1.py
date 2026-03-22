import subprocess
import unittest
from pathlib import Path


class RunAgentModelicaNowV1Tests(unittest.TestCase):
    def test_help_shows_commands(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_now_v1.sh"
        proc = subprocess.run(
            ["bash", str(script), "--help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("calib", proc.stdout)
        self.assertIn("loop-mini-live", proc.stdout)
        self.assertIn("preflight", proc.stdout)

    def test_unknown_command_returns_nonzero(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_now_v1.sh"
        proc = subprocess.run(
            ["bash", str(script), "unknown-cmd"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertNotEqual(proc.returncode, 0)
        merged = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("unknown command", merged)

    def test_preflight_defaults_to_v015_wrapper(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_now_v1.sh").read_text(encoding="utf-8")
        self.assertIn("bash scripts/run_agent_modelica_release_preflight_v0_1_5.sh", script)


if __name__ == "__main__":
    unittest.main()
