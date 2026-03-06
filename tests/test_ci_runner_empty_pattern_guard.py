import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class CIShardRunnerEmptyPatternGuardTests(unittest.TestCase):
    def test_ci_runner_fails_when_pattern_matches_no_tests(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "ci_run_unittest_shard.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script), "test_no_such_pattern_12345.py"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "CI_LOG_DIR": d, "CI_FAIL_ON_EMPTY_PATTERN": "1"},
                timeout=60,
            )
            merged = (proc.stdout or "") + "\n" + (proc.stderr or "")
            self.assertEqual(proc.returncode, 86, msg=merged)
            self.assertIn("empty-test-pattern detected", merged)

    def test_ci_runner_allows_empty_pattern_when_guard_disabled(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "ci_run_unittest_shard.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script), "test_no_such_pattern_12345.py"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "CI_LOG_DIR": d, "CI_FAIL_ON_EMPTY_PATTERN": "0"},
                timeout=60,
            )
            merged = (proc.stdout or "") + "\n" + (proc.stderr or "")
            self.assertNotEqual(proc.returncode, 86, msg=merged)
            self.assertIn("NO TESTS RAN", merged)


if __name__ == "__main__":
    unittest.main()
