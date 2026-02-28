import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetOptionalCIContractTests(unittest.TestCase):
    def test_dataset_optional_chain_writes_required_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "artifacts"
            self._write_required_files(root)
            out = root / "contract" / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_optional_ci_contract",
                    "--artifacts-root",
                    str(root),
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
            self.assertEqual(payload.get("fail_count"), 0)

    def test_dataset_optional_chain_summary_schema(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "artifacts"
            self._write_required_files(root)
            # Corrupt one summary by deleting required key.
            bad = root / "dataset_artifacts_pipeline_demo" / "summary.json"
            bad_payload = json.loads(bad.read_text(encoding="utf-8"))
            bad_payload.pop("quality_gate_status", None)
            bad.write_text(json.dumps(bad_payload), encoding="utf-8")
            out = root / "contract" / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_optional_ci_contract",
                    "--artifacts-root",
                    str(root),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            failed = [x for x in payload.get("checks", []) if x.get("status") == "FAIL"]
            self.assertTrue(failed)
            self.assertIn("quality_gate_status", failed[0].get("missing_keys", []))

    def _write_required_files(self, root: Path) -> None:
        mapping = {
            "dataset_pipeline_demo/summary.json": {"bundle_status": "PASS", "result_flags": {}},
            "dataset_artifacts_pipeline_demo/summary.json": {"bundle_status": "PASS", "quality_gate_status": "PASS"},
            "dataset_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_governance_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_policy_lifecycle_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_governance_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_strategy_autotune_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_strategy_autotune_apply_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_strategy_autotune_apply_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_governance_snapshot_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "promotion_effectiveness_history_trend_status": "NEEDS_REVIEW",
                "failure_taxonomy_coverage_status": "PASS",
                "failure_taxonomy_missing_model_scales_count": 0,
                "failure_distribution_benchmark_status": "PASS",
                "failure_distribution_drift_score": 0.12,
                "model_scale_ladder_status": "PASS",
                "model_scale_large_ready": True,
                "failure_policy_patch_advisor_status": "PASS",
                "failure_policy_patch_suggested_action": "keep",
                "modelica_library_provenance_guard_status": "PASS",
                "modelica_library_provenance_completeness_pct": 99.0,
                "large_model_benchmark_pack_status": "PASS",
                "large_model_benchmark_pack_readiness_score": 86.0,
                "mutation_campaign_tracker_status": "PASS",
                "mutation_campaign_completion_ratio_pct": 91.0,
                "moat_public_scoreboard_status": "PASS",
                "moat_public_score": 84.0,
                "real_model_license_compliance_status": "PASS",
                "real_model_license_compliance_unknown_license_ratio_pct": 0.0,
                "modelica_mutation_recipe_library_status": "PASS",
                "modelica_mutation_recipe_total": 10,
                "real_model_failure_yield_status": "PASS",
                "real_model_failure_yield_per_accepted_model": 1.7,
                "real_model_intake_backlog_status": "PASS",
                "real_model_intake_backlog_p0_count": 0,
                "modelica_moat_readiness_gate_status": "PASS",
                "modelica_moat_readiness_score": 83.0,
                "real_model_supply_health_status": "PASS",
                "real_model_supply_health_score": 84.0,
                "mutation_recipe_execution_audit_status": "PASS",
                "mutation_recipe_execution_coverage_pct": 81.0,
                "modelica_release_candidate_gate_status": "PASS",
                "modelica_release_candidate_score": 84.0,
                "milestone_checkpoint_status": "PASS",
                "milestone_checkpoint_score": 84.0,
                "milestone_public_brief_status": "PASS",
                "intake_growth_advisor_status": "PASS",
                "intake_growth_suggested_action": "keep",
                "intake_growth_advisor_history_status": "PASS",
                "intake_growth_advisor_history_trend_status": "PASS",
                "intake_growth_execution_board_status": "PASS",
                "intake_growth_execution_board_execution_score": 84.0,
                "intake_growth_execution_board_history_status": "PASS",
                "intake_growth_execution_board_history_trend_status": "PASS",
                "real_model_intake_portfolio_status": "PASS",
                "real_model_intake_portfolio_total_real_models": 4,
                "real_model_intake_portfolio_large_models": 1,
                "mutation_coverage_depth_status": "PASS",
                "mutation_coverage_depth_score": 91.0,
                "failure_distribution_stability_status": "PASS",
                "failure_distribution_stability_score": 83.0,
                "failure_distribution_stability_rare_failure_replay_rate": 1.0,
                "moat_anchor_brief_status": "PASS",
                "moat_anchor_brief_score": 82.0,
                "moat_anchor_brief_recommendation": "PUBLISH",
                "moat_anchor_brief_history_status": "PASS",
                "moat_anchor_brief_history_publish_rate": 0.75,
                "moat_anchor_brief_history_trend_status": "PASS",
            },
            "dataset_governance_snapshot_trend_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "status_transition": "PASS->PASS",
                "promotion_effectiveness_history_trend_transition": "PASS->NEEDS_REVIEW",
                "failure_taxonomy_coverage_status_transition": "PASS->PASS",
                "failure_distribution_benchmark_status_transition": "PASS->PASS",
                "model_scale_ladder_status_transition": "PASS->PASS",
                "failure_policy_patch_advisor_status_transition": "PASS->PASS",
                "modelica_library_provenance_guard_status_transition": "PASS->PASS",
                "large_model_benchmark_pack_status_transition": "PASS->PASS",
                "mutation_campaign_tracker_status_transition": "PASS->PASS",
                "moat_public_scoreboard_status_transition": "PASS->PASS",
                "real_model_license_compliance_status_transition": "PASS->PASS",
                "modelica_mutation_recipe_library_status_transition": "PASS->PASS",
                "real_model_failure_yield_status_transition": "PASS->PASS",
                "real_model_intake_backlog_status_transition": "PASS->PASS",
                "modelica_moat_readiness_gate_status_transition": "PASS->PASS",
                "real_model_supply_health_status_transition": "PASS->PASS",
                "mutation_recipe_execution_audit_status_transition": "PASS->PASS",
                "modelica_release_candidate_gate_status_transition": "PASS->PASS",
                "milestone_checkpoint_status_transition": "PASS->PASS",
                "milestone_checkpoint_trend_status_transition": "PASS->PASS",
                "milestone_public_brief_status_transition": "PASS->PASS",
                "intake_growth_advisor_status_transition": "PASS->PASS",
                "intake_growth_advisor_history_status_transition": "PASS->PASS",
                "intake_growth_advisor_history_trend_status_transition": "PASS->PASS",
                "intake_growth_execution_board_status_transition": "PASS->PASS",
                "intake_growth_execution_board_history_status_transition": "PASS->PASS",
                "intake_growth_execution_board_history_trend_status_transition": "PASS->PASS",
                "real_model_intake_portfolio_status_transition": "PASS->PASS",
                "mutation_coverage_depth_status_transition": "PASS->PASS",
                "failure_distribution_stability_status_transition": "PASS->PASS",
                "moat_anchor_brief_status_transition": "PASS->PASS",
                "moat_anchor_brief_history_status_transition": "PASS->PASS",
                "moat_anchor_brief_history_trend_status_transition": "PASS->PASS",
                "status_delta_alert_count": 1,
                "severity_level": "medium",
            },
            "dataset_failure_taxonomy_coverage_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "coverage_status": "PASS",
                "missing_model_scales_count": 0,
            },
            "dataset_failure_distribution_benchmark_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "benchmark_status": "PASS",
                "distribution_drift_score": 0.1,
            },
            "dataset_model_scale_ladder_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "ladder_status": "PASS",
                "large_ready": True,
            },
            "dataset_failure_policy_patch_advisor_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "advisor_status": "PASS",
                "suggested_action": "keep",
            },
            "dataset_blind_spot_backlog_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "backlog_status": "NEEDS_REVIEW",
                "total_open_tasks": 3,
            },
            "dataset_policy_patch_replay_evaluator_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "evaluator_status": "PASS",
                "recommendation": "ADOPT_PATCH",
            },
            "dataset_governance_evidence_pack_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "evidence_pack_status": "PASS",
                "evidence_strength_score": 78,
                "backlog_open_tasks": 3,
                "policy_patch_roi_score": 67,
            },
            "dataset_moat_trend_snapshot_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "moat_status": "PASS",
                "moat_score": 74.2,
                "execution_readiness_index": 82.0,
                "moat_score_delta": 6.5,
            },
            "dataset_external_proof_score_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "proof_status": "PASS",
                "proof_score": 82.0,
                "execution_readiness_index": 82.0,
            },
            "dataset_backlog_execution_bridge_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "bridge_status": "NEEDS_REVIEW",
                "total_execution_tasks": 3,
            },
            "dataset_replay_quality_guard_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "guard_status": "PASS",
                "confidence_level": "high",
            },
            "dataset_promotion_candidate_demo/summary.json": {
                "bundle_status": "PASS",
                "decision": "HOLD",
            },
            "dataset_promotion_candidate_apply_demo/summary.json": {
                "bundle_status": "PASS",
            },
            "dataset_promotion_candidate_history_demo/summary.json": {
                "bundle_status": "PASS",
            },
            "dataset_promotion_candidate_apply_history_demo/summary.json": {
                "bundle_status": "PASS",
            },
            "dataset_promotion_effectiveness_demo/summary.json": {
                "bundle_status": "PASS",
                "effectiveness_decision": "KEEP",
            },
            "dataset_promotion_effectiveness_history_demo/summary.json": {
                "bundle_status": "PASS",
                "trend_status": "NEEDS_REVIEW",
            },
            "dataset_policy_autotune_history_demo/summary.json": {"bundle_status": "PASS"},
            "dataset_modelica_library_provenance_guard_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "guard_status": "PASS",
                "provenance_completeness_pct": 99.0,
                "unknown_license_ratio_pct": 0.0,
            },
            "dataset_large_model_benchmark_pack_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "pack_status": "PASS",
                "pack_readiness_score": 86.0,
                "selected_large_models": 3,
                "selected_large_mutations": 8,
            },
            "dataset_mutation_campaign_tracker_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "tracker_status": "PASS",
                "campaign_phase": "scale_out",
                "completion_ratio_pct": 90.0,
            },
            "dataset_moat_public_scoreboard_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "scoreboard_status": "PASS",
                "moat_public_score": 84.0,
                "verdict": "EMERGING_MOAT",
            },
            "dataset_real_model_license_compliance_gate_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "license_gate_status": "PASS",
            },
            "dataset_modelica_mutation_recipe_library_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "recipe_library_status": "PASS",
            },
            "dataset_real_model_failure_yield_tracker_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "yield_tracker_status": "PASS",
            },
            "dataset_real_model_intake_backlog_prioritizer_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "backlog_prioritizer_status": "NEEDS_REVIEW",
            },
            "dataset_modelica_moat_readiness_gate_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "moat_gate_status": "PASS",
            },
            "dataset_real_model_supply_health_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "supply_health_status": "PASS",
                "supply_health_score": 84.0,
            },
            "dataset_mutation_recipe_execution_audit_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "audit_status": "PASS",
                "execution_coverage_pct": 81.0,
            },
            "dataset_real_model_intake_portfolio_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "portfolio_status": "PASS",
                "total_real_models": 4,
                "large_models": 1,
            },
            "dataset_mutation_coverage_depth_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "coverage_status": "PASS",
                "coverage_depth_score": 91.0,
                "uncovered_cells_count": 1,
            },
            "dataset_failure_distribution_stability_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "stability_status": "PASS",
                "stability_score": 83.0,
                "rare_failure_replay_rate": 1.0,
            },
            "dataset_moat_anchor_brief_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "anchor_brief_status": "PASS",
                "anchor_brief_score": 82.0,
                "recommendation": "PUBLISH",
            },
            "dataset_moat_anchor_brief_history_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "history_status": "PASS",
                "total_records": 4,
                "avg_anchor_brief_score": 79.0,
            },
            "dataset_moat_anchor_brief_history_trend_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "trend_status": "PASS",
                "status_transition": "PASS->PASS",
                "recommendation_transition": "PUBLISH->PUBLISH",
            },
            "dataset_modelica_release_candidate_gate_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "release_candidate_status": "PASS",
                "candidate_decision": "GO",
            },
            "dataset_intake_growth_advisor_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "advisor_status": "PASS",
                "suggested_action": "keep",
            },
            "dataset_intake_growth_advisor_history_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "history_status": "PASS",
                "latest_suggested_action": "keep",
            },
            "dataset_intake_growth_advisor_history_trend_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "trend_status": "PASS",
                "status_transition": "PASS->PASS",
            },
            "dataset_intake_growth_execution_board_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "board_status": "PASS",
                "execution_score": 84.0,
            },
            "dataset_intake_growth_execution_board_history_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "history_status": "PASS",
                "avg_execution_score": 82.0,
            },
            "dataset_intake_growth_execution_board_history_trend_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "trend_status": "PASS",
                "status_transition": "PASS->PASS",
            },
            "dataset_milestone_checkpoint_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "checkpoint_status": "PASS",
                "milestone_decision": "ready_for_external_validation",
            },
            "dataset_milestone_checkpoint_trend_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "trend_status": "PASS",
                "status_transition": "PASS->PASS",
            },
            "dataset_milestone_public_brief_v1_demo/demo_summary.json": {
                "bundle_status": "PASS",
                "brief_status": "PASS",
            },
        }
        for rel, payload in mapping.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
