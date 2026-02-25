import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceSnapshotTrendDemoTests(unittest.TestCase):
    def test_demo_dataset_governance_snapshot_trend_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_governance_snapshot_trend.sh"
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
                (repo_root / "artifacts" / "dataset_governance_snapshot_trend_demo" / "demo_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIn("->", str(payload.get("status_transition")))
            self.assertIn("->", str(payload.get("promotion_effectiveness_history_trend_transition")))
            self.assertIsInstance(payload.get("status_delta_alert_count"), int)
            self.assertIsInstance(payload.get("severity_score"), int)
            self.assertIn(payload.get("severity_level"), {"low", "medium", "high"})


if __name__ == "__main__":
    unittest.main()
