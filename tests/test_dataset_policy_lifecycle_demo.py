import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyLifecycleDemoTests(unittest.TestCase):
    def test_demo_dataset_policy_lifecycle_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_policy_lifecycle.sh"
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
            payload = json.loads(
                (repo_root / "artifacts" / "dataset_policy_lifecycle_demo" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIn(payload.get("effectiveness_decision"), {"KEEP", "NEEDS_REVIEW", "ROLLBACK_REVIEW"})


if __name__ == "__main__":
    unittest.main()

