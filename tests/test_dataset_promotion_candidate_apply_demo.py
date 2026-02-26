import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionCandidateApplyDemoTests(unittest.TestCase):
    def test_demo_dataset_promotion_candidate_apply_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_promotion_candidate_apply.sh"
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
                (
                    repo_root / "artifacts" / "dataset_promotion_candidate_apply_demo" / "summary.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIsInstance(payload.get("active_dataset_promotion_decision"), str)


if __name__ == "__main__":
    unittest.main()
