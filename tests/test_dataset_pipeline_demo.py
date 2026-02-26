import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetPipelineDemoTests(unittest.TestCase):
    def test_demo_dataset_pipeline_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_pipeline.sh"
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
                (repo_root / "artifacts" / "dataset_pipeline_demo" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertEqual(payload.get("quality_gate_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
