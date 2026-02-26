import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneGovernanceAdvisorDemoTests(unittest.TestCase):
    def test_demo_script(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                ["bash", "scripts/demo_policy_autotune_governance_advisor.sh"],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "TMPDIR": d, "GATEFORGE_DEMO_FAST": "1"},
                timeout=300,
            )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(
            Path("artifacts/policy_autotune_governance_advisor_demo/summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertIn(payload.get("advisor_action"), {"KEEP", "TIGHTEN", "ROLLBACK_REVIEW"})


if __name__ == "__main__":
    unittest.main()
