import unittest
from pathlib import Path


class CIShardRunnerContractTests(unittest.TestCase):
    def test_ci_runner_keeps_compatibility_and_failure_diagnostics(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "ci_run_unittest_shard.sh").read_text(encoding="utf-8")

        required_fragments = [
            'PATTERNS_CSV="${1:-test_*.py}"',
            'IFS=\',\' read -r -a PATTERNS <<< "$PATTERNS_CSV"',
            'command -v timeout',
            'command -v gtimeout',
            'PYTHON_BIN="python"',
            'PYTHON_BIN="python3"',
            'warning: timeout command not found; running shard without enforced timeout',
            '-X faulthandler -m unittest discover -s tests -p "$PATTERN" -v',
            '[ci] shard summary patterns=$PATTERNS_CSV',
            'echo "[ci] shard failed: pattern=$failed_pattern exit_code=$rc"',
            'last running test before failure',
            'echo "[ci] shard timed out after $SHARD_TIMEOUT"',
            'tail -n 80 "$LOG_FILE"',
            'exit "$rc"',
        ]

        missing = [frag for frag in required_fragments if frag not in script]
        self.assertFalse(
            missing,
            msg="ci shard runner must preserve compatibility and diagnostics: " + ", ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
