import json
import subprocess
import unittest
from pathlib import Path


class GovernancePolicyPatchExplainableFlowDemoTests(unittest.TestCase):
    def test_demo_script(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_governance_policy_patch_explainable_flow.sh"],
            capture_output=True,
            text=True,
            check=False,
                timeout=120,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        payload = json.loads(
            Path("artifacts/governance_policy_patch_explainable_demo/summary.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("preview_status"), "PREVIEW")
        self.assertEqual(payload.get("apply_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
