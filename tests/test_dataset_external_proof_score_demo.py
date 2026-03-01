import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetExternalProofScoreDemoTests(unittest.TestCase):
    def test_demo_dataset_external_proof_score_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_external_proof_score.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(["bash", str(script)], cwd=str(repo_root), capture_output=True, text=True, check=False, env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"}, timeout=120)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((repo_root / "artifacts" / "dataset_external_proof_score_demo" / "demo_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertIsInstance(payload.get("execution_readiness_index"), (int, float))
            self.assertIsInstance(payload.get("target_gap_pressure_index"), (int, float))
            self.assertIsInstance(payload.get("model_asset_target_gap_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
