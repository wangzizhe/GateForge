import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetStrategyAutotuneDemoTests(unittest.TestCase):
    def test_demo_dataset_strategy_autotune_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_strategy_autotune.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
                env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(
                (repo_root / "artifacts" / "dataset_strategy_autotune_demo" / "summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIsInstance(payload.get("suggested_action"), str)


if __name__ == "__main__":
    unittest.main()

