import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionEffectivenessHistoryDemoTests(unittest.TestCase):
    def test_demo_dataset_promotion_effectiveness_history_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_promotion_effectiveness_history.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "TMPDIR": d},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(
                (
                    repo_root / "artifacts" / "dataset_promotion_effectiveness_history_demo" / "summary.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIn(payload.get("trend_status"), {"PASS", "NEEDS_REVIEW"})


if __name__ == "__main__":
    unittest.main()
