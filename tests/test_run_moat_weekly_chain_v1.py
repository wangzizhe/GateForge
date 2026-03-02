import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunMoatWeeklyChainV1Tests(unittest.TestCase):
    def test_run_moat_weekly_chain_v1_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_moat_weekly_chain_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(
                (
                    repo_root
                    / "artifacts"
                    / "dataset_moat_weekly_chain_v1"
                    / "summary.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
