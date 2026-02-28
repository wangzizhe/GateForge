import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelSupplyPipelineV1Tests(unittest.TestCase):
    def test_pipeline_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            backlog = root / "backlog.json"
            license_summary = root / "license.json"
            growth = root / "growth.json"
            out = root / "summary.json"
            intake.write_text(json.dumps({"status": "PASS", "accepted_count": 5, "accepted_large_count": 2, "reject_rate_pct": 18.0}), encoding="utf-8")
            backlog.write_text(json.dumps({"status": "PASS", "backlog_item_count": 3, "p0_count": 0}), encoding="utf-8")
            license_summary.write_text(json.dumps({"status": "PASS", "disallowed_license_count": 0, "unknown_license_ratio_pct": 0.0}), encoding="utf-8")
            growth.write_text(json.dumps({"status": "PASS", "delta_total_real_models": 2, "delta_large_models": 1, "growth_velocity_score": 82.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_supply_pipeline_v1",
                    "--real-model-intake-summary",
                    str(intake),
                    "--real-model-intake-backlog-summary",
                    str(backlog),
                    "--real-model-license-compliance-summary",
                    str(license_summary),
                    "--real-model-growth-trend-summary",
                    str(growth),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")

    def test_pipeline_needs_review_when_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            intake = root / "intake.json"
            backlog = root / "backlog.json"
            license_summary = root / "license.json"
            growth = root / "growth.json"
            out = root / "summary.json"
            intake.write_text(json.dumps({"status": "PASS", "accepted_count": 4, "accepted_large_count": 1, "reject_rate_pct": 40.0}), encoding="utf-8")
            backlog.write_text(json.dumps({"status": "NEEDS_REVIEW", "backlog_item_count": 4, "p0_count": 2}), encoding="utf-8")
            license_summary.write_text(json.dumps({"status": "NEEDS_REVIEW", "disallowed_license_count": 1, "unknown_license_ratio_pct": 10.0}), encoding="utf-8")
            growth.write_text(json.dumps({"status": "NEEDS_REVIEW", "delta_total_real_models": 0, "delta_large_models": 0, "growth_velocity_score": 48.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_supply_pipeline_v1",
                    "--real-model-intake-summary",
                    str(intake),
                    "--real-model-intake-backlog-summary",
                    str(backlog),
                    "--real-model-license-compliance-summary",
                    str(license_summary),
                    "--real-model-growth-trend-summary",
                    str(growth),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("license_blockers_present", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
