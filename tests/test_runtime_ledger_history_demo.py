import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RuntimeLedgerHistoryDemoTests(unittest.TestCase):
    def test_demo_runtime_decision_ledger_history_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_runtime_decision_ledger_history.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
                env={**os.environ, "TMPDIR": d},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary_path = repo_root / "artifacts" / "runtime_decision_ledger_history_demo" / "summary.json"
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
