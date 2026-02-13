import json
import subprocess
import unittest
from pathlib import Path


class DemoScriptTests(unittest.TestCase):
    def test_demo_all_script_writes_bundle_summary(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_all.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

        summary_json = Path("artifacts/demo_all_summary.json")
        summary_md = Path("artifacts/demo_all_summary.md")
        self.assertTrue(summary_json.exists())
        self.assertTrue(summary_md.exists())

        payload = json.loads(summary_json.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("bundle_status"), "PASS")
        self.assertEqual(payload.get("proposal_flow_status"), "PASS")
        self.assertEqual(payload.get("checker_demo_status"), "FAIL")
        self.assertIsInstance(payload.get("proposal_fail_reasons_count"), int)
        self.assertIsInstance(payload.get("checker_reasons_count"), int)
        self.assertIsInstance(payload.get("checker_findings_count"), int)

        result_flags = payload.get("result_flags", {})
        self.assertEqual(result_flags.get("proposal_flow"), "PASS")
        self.assertEqual(result_flags.get("checker_demo_expected_fail"), "PASS")
        checksums = payload.get("checksums", {})
        self.assertIsInstance(checksums, dict)
        artifacts = payload.get("artifacts", [])
        for artifact in artifacts:
            self.assertIn(artifact, checksums)
            self.assertEqual(len(checksums[artifact]), 64)

    def test_demo_autopilot_dry_run_script_writes_review_template(self) -> None:
        proc = subprocess.run(
            ["bash", "scripts/demo_autopilot_dry_run.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

        out_json = Path("artifacts/autopilot/autopilot_dry_run_demo.json")
        out_md = Path("artifacts/autopilot/autopilot_dry_run_demo.md")
        self.assertTrue(out_json.exists())
        self.assertTrue(out_md.exists())

        payload = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("status"), "PLANNED")
        self.assertEqual(payload.get("planned_risk_level"), "high")
        checks = payload.get("planned_required_human_checks", [])
        self.assertTrue(checks)
        self.assertTrue(any("rollback" in c.lower() for c in checks))


if __name__ == "__main__":
    unittest.main()
