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
                            "dataset_failure_distribution_benchmark_status": "PASS",
                            "dataset_failure_distribution_detection_rate_after": 0.82,
                            "dataset_failure_distribution_false_positive_rate_after": 0.04,
                            "dataset_failure_distribution_regression_rate_after": 0.09,
                            "dataset_failure_distribution_drift_score": 0.2,
                            "dataset_model_scale_ladder_status": "PASS",
                            "dataset_model_scale_medium_cases": 2,
                            "dataset_model_scale_large_cases": 1,
                            "dataset_model_scale_main_ci_lane_count": 2,
                            "dataset_failure_policy_patch_advisor_status": "PASS",
                            "dataset_failure_policy_patch_confidence": 0.64,
                            "dataset_failure_policy_patch_reason_count": 1,
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
                            "dataset_failure_distribution_benchmark_status": "NEEDS_REVIEW",
                            "dataset_failure_distribution_detection_rate_after": 0.73,
                            "dataset_failure_distribution_false_positive_rate_after": 0.11,
                            "dataset_failure_distribution_regression_rate_after": 0.22,
                            "dataset_failure_distribution_drift_score": 0.38,
                            "dataset_model_scale_ladder_status": "NEEDS_REVIEW",
                            "dataset_model_scale_medium_cases": 3,
                            "dataset_model_scale_large_cases": 0,
                            "dataset_model_scale_main_ci_lane_count": 1,
                            "dataset_failure_policy_patch_advisor_status": "NEEDS_REVIEW",
                            "dataset_failure_policy_patch_confidence": 0.87,
                            "dataset_failure_policy_patch_reason_count": 4,
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
            self.assertIn(
                "failure_distribution_benchmark_worsened",
                (trend.get("status_delta") or {}).get("alerts", []),
            )
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_failure_distribution_benchmark_status_transition"),
                "PASS->NEEDS_REVIEW",
            )
            self.assertEqual(
                (trend.get("kpi_delta") or {}).get("dataset_failure_distribution_detection_rate_after_delta"),
                -0.09,
            )
            self.assertIn("model_scale_ladder_worsened", (trend.get("status_delta") or {}).get("alerts", []))
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_model_scale_ladder_status_transition"),
                "PASS->NEEDS_REVIEW",
            )
            self.assertIn("failure_policy_patch_advisor_worsened", (trend.get("status_delta") or {}).get("alerts", []))
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_failure_policy_patch_advisor_status_transition"),
                "PASS->NEEDS_REVIEW",
            )
            self.assertIn(
                "dataset_real_model_license_compliance_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_modelica_mutation_recipe_library_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_failure_yield_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_intake_backlog_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_modelica_moat_readiness_gate_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_supply_health_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_mutation_recipe_execution_audit_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_modelica_release_candidate_gate_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_intake_growth_advisor_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_intake_growth_advisor_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_intake_growth_advisor_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_intake_growth_execution_board_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_intake_growth_execution_board_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_intake_growth_execution_board_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_intake_portfolio_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_mutation_coverage_depth_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_failure_distribution_stability_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_failure_distribution_stability_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_failure_distribution_stability_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_moat_anchor_brief_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_moat_anchor_brief_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_moat_anchor_brief_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_supply_pipeline_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_mutation_coverage_matrix_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_intake_board_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_intake_board_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_anchor_model_pack_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_anchor_model_pack_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_failure_matrix_expansion_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_failure_matrix_expansion_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_momentum_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_momentum_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_momentum_history_trend_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_target_gap_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_target_gap_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_target_gap_history_trend_status_transition",
                trend.get("status_delta") or {},
            )

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
                            "dataset_failure_distribution_benchmark_status": "PASS",
                            "dataset_failure_distribution_detection_rate_after": 0.9,
                            "dataset_failure_distribution_false_positive_rate_after": 0.03,
                            "dataset_failure_distribution_regression_rate_after": 0.08,
                            "dataset_failure_distribution_drift_score": 0.1,
                            "dataset_model_scale_ladder_status": "PASS",
                            "dataset_model_scale_medium_cases": 3,
                            "dataset_model_scale_large_cases": 2,
                            "dataset_model_scale_main_ci_lane_count": 2,
                            "dataset_failure_policy_patch_advisor_status": "PASS",
                            "dataset_failure_policy_patch_confidence": 0.64,
                            "dataset_failure_policy_patch_reason_count": 1,
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
                            "dataset_failure_distribution_benchmark_status": "PASS",
                            "dataset_failure_distribution_detection_rate_after": 0.9,
                            "dataset_failure_distribution_false_positive_rate_after": 0.03,
                            "dataset_failure_distribution_regression_rate_after": 0.08,
                            "dataset_failure_distribution_drift_score": 0.1,
                            "dataset_model_scale_ladder_status": "PASS",
                            "dataset_model_scale_medium_cases": 3,
                            "dataset_model_scale_large_cases": 2,
                            "dataset_model_scale_main_ci_lane_count": 2,
                            "dataset_failure_policy_patch_advisor_status": "PASS",
                            "dataset_failure_policy_patch_confidence": 0.64,
                            "dataset_failure_policy_patch_reason_count": 1,
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
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_failure_distribution_benchmark_status_transition"),
                "PASS->PASS",
            )
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_model_scale_ladder_status_transition"),
                "PASS->PASS",
            )
            self.assertEqual(
                (trend.get("status_delta") or {}).get("dataset_failure_policy_patch_advisor_status_transition"),
                "PASS->PASS",
            )
            self.assertIn(
                "dataset_real_model_license_compliance_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_modelica_mutation_recipe_library_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_failure_yield_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_intake_backlog_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_modelica_moat_readiness_gate_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_real_model_supply_health_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_mutation_recipe_execution_audit_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_modelica_release_candidate_gate_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_target_gap_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_target_gap_history_status_transition",
                trend.get("status_delta") or {},
            )
            self.assertIn(
                "dataset_model_asset_target_gap_history_trend_status_transition",
                trend.get("status_delta") or {},
            )


if __name__ == "__main__":
    unittest.main()
