import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceSnapshotTrendTests(unittest.TestCase):
    def test_trend_detects_new_risks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": ["dataset_history_trend_needs_review"],
                        "kpis": {
                            "dataset_pipeline_deduplicated_cases": 10,
                            "dataset_pipeline_failure_case_rate": 0.2,
                            "dataset_governance_total_records": 5,
                            "dataset_governance_trend_alert_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "risks": ["dataset_governance_trend_needs_review"],
                        "kpis": {
                            "dataset_pipeline_deduplicated_cases": 12,
                            "dataset_pipeline_failure_case_rate": 0.3,
                            "dataset_governance_total_records": 7,
                            "dataset_governance_trend_alert_count": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot_trend",
                    "--summary",
                    str(current),
                    "--previous-summary",
                    str(previous),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("status_transition"), "PASS->NEEDS_REVIEW")
            self.assertIn("dataset_governance_trend_needs_review", trend.get("new_risks", []))
            self.assertIn("dataset_history_trend_needs_review", trend.get("resolved_risks", []))
            self.assertIn("dataset_pipeline_failure_case_rate_delta", trend.get("kpi_delta", {}))

    def test_trend_marks_pass_when_kpis_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "dataset_pipeline_deduplicated_cases": 10,
                            "dataset_pipeline_failure_case_rate": 0.2,
                            "dataset_governance_total_records": 5,
                            "dataset_governance_trend_alert_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "dataset_pipeline_deduplicated_cases": 10,
                            "dataset_pipeline_failure_case_rate": 0.2,
                            "dataset_governance_total_records": 5,
                            "dataset_governance_trend_alert_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_snapshot_trend",
                    "--summary",
                    str(current),
                    "--previous-summary",
                    str(previous),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("status_transition"), "PASS->PASS")
            self.assertEqual(trend.get("new_risks", []), [])
            self.assertEqual(trend.get("resolved_risks", []), [])


if __name__ == "__main__":
    unittest.main()
