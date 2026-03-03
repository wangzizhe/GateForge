import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunModelicaOpenSourceBootstrapV1DemoTests(unittest.TestCase):
    def test_demo_run_modelica_open_source_bootstrap_v1_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_run_modelica_open_source_bootstrap_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(
                (
                    repo_root
                    / "artifacts"
                    / "run_modelica_open_source_bootstrap_v1_demo"
                    / "demo_summary.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
