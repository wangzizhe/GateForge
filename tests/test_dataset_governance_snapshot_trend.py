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
                            "dataset_failure_taxonomy_coverage_status": "PASS",
                            "dataset_failure_taxonomy_total_cases": 5,
                            "dataset_failure_taxonomy_unique_failure_types": 3,
                            "dataset_failure_taxonomy_missing_failure_types_count": 2,
                            "dataset_failure_taxonomy_missing_model_scales_count": 1,
                            "dataset_promotion_effectiveness_history_trend_status": "PASS",
                            "dataset_promotion_effectiveness_history_latest_decision": "KEEP",
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
                            "dataset_failure_taxonomy_coverage_status": "NEEDS_REVIEW",
                            "dataset_failure_taxonomy_total_cases": 8,
                            "dataset_failure_taxonomy_unique_failure_types": 4,
                            "dataset_failure_taxonomy_missing_failure_types_count": 1,
                            "dataset_failure_taxonomy_missing_model_scales_count": 0,
                            "dataset_promotion_effectiveness_history_trend_status": "NEEDS_REVIEW",
                            "dataset_promotion_effectiveness_history_latest_decision": "ROLLBACK_REVIEW",
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
            self.assertGreaterEqual(int(trend.get("severity_score", 0) or 0), 1)
            self.assertIn(trend.get("severity_level"), {"medium", "high"})
            self.assertEqual(
                (trend.get("status_delta") or {}).get(
                    "dataset_promotion_effectiveness_history_trend_status_transition"
                ),
                "PASS->NEEDS_REVIEW",
            )
            self.assertIn(
                "promotion_effectiveness_history_trend_worsened",
                (trend.get("status_delta") or {}).get("alerts", []),
            )
            self.assertIn("failure_taxonomy_coverage_worsened", (trend.get("status_delta") or {}).get("alerts", []))
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_failure_taxonomy_coverage_status_transition"),
                "PASS->NEEDS_REVIEW",
            )
            self.assertEqual((trend.get("kpi_delta") or {}).get("dataset_failure_taxonomy_total_cases_delta"), 3.0)

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
                            "dataset_failure_taxonomy_coverage_status": "PASS",
                            "dataset_failure_taxonomy_total_cases": 10,
                            "dataset_failure_taxonomy_unique_failure_types": 5,
                            "dataset_failure_taxonomy_missing_failure_types_count": 0,
                            "dataset_failure_taxonomy_missing_model_scales_count": 0,
                            "dataset_promotion_effectiveness_history_trend_status": "PASS",
                            "dataset_promotion_effectiveness_history_latest_decision": "KEEP",
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
                            "dataset_failure_taxonomy_coverage_status": "PASS",
                            "dataset_failure_taxonomy_total_cases": 10,
                            "dataset_failure_taxonomy_unique_failure_types": 5,
                            "dataset_failure_taxonomy_missing_failure_types_count": 0,
                            "dataset_failure_taxonomy_missing_model_scales_count": 0,
                            "dataset_promotion_effectiveness_history_trend_status": "PASS",
                            "dataset_promotion_effectiveness_history_latest_decision": "KEEP",
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
            self.assertEqual(int(trend.get("severity_score", 0) or 0), 0)
            self.assertEqual(trend.get("severity_level"), "low")
            self.assertEqual(
                (trend.get("status_delta") or {}).get(
                    "dataset_promotion_effectiveness_history_latest_decision_transition"
                ),
                "KEEP->KEEP",
            )
            self.assertEqual((trend.get("status_delta") or {}).get("alerts", []), [])
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_failure_taxonomy_coverage_status_transition"),
                "PASS->PASS",
            )


if __name__ == "__main__":
    unittest.main()
