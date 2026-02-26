import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DatasetOptionalCIContractDemoTests(unittest.TestCase):
    def test_demo_dataset_optional_ci_contract_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "demo_dataset_optional_ci_contract.sh"
        with tempfile.TemporaryDirectory() as d:
            try:
                proc = subprocess.run(
                    ["bash", str(script)],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
                    timeout=120,
                )
            except subprocess.TimeoutExpired as exc:
                self.fail(f"demo timed out after {exc.timeout}s")
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(
                (
                    repo_root / "artifacts" / "dataset_optional_ci_contract_demo" / "demo_summary.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(payload.get("bundle_status"), "PASS")
            self.assertEqual(payload.get("contract_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
