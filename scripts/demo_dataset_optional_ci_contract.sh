#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_optional_ci_contract_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ]; then
  python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts")
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
        "promotion_effectiveness_history_trend_status": "PASS",
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
        "mutation_campaign_completion_ratio_pct": 90.0,
        "moat_public_scoreboard_status": "PASS",
        "moat_public_score": 85.0,
        "real_model_license_compliance_status": "PASS",
        "real_model_license_compliance_unknown_license_ratio_pct": 0.0,
        "modelica_mutation_recipe_library_status": "PASS",
        "modelica_mutation_recipe_total": 10,
        "real_model_failure_yield_status": "PASS",
        "real_model_failure_yield_per_accepted_model": 1.8,
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
        "failure_distribution_stability_history_status": "PASS",
        "failure_distribution_stability_history_avg_stability_score": 80.0,
        "failure_distribution_stability_history_trend_status": "PASS",
        "moat_anchor_brief_status": "PASS",
        "moat_anchor_brief_score": 82.0,
        "moat_anchor_brief_recommendation": "PUBLISH",
        "moat_anchor_brief_history_status": "PASS",
        "moat_anchor_brief_history_publish_rate": 0.75,
        "moat_anchor_brief_history_trend_status": "PASS",
        "real_model_supply_pipeline_status": "PASS",
        "real_model_supply_pipeline_score": 84.0,
        "real_model_supply_pipeline_new_models_30d": 2,
        "mutation_coverage_matrix_status": "PASS",
        "mutation_coverage_matrix_score": 83.0,
        "mutation_coverage_matrix_high_risk_uncovered_cells": 1,
    },
    "dataset_governance_snapshot_trend_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "status_transition": "PASS->PASS",
        "promotion_effectiveness_history_trend_transition": "PASS->PASS",
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
        "failure_distribution_stability_history_status_transition": "PASS->PASS",
        "failure_distribution_stability_history_trend_status_transition": "PASS->PASS",
        "moat_anchor_brief_status_transition": "PASS->PASS",
        "moat_anchor_brief_history_status_transition": "PASS->PASS",
        "moat_anchor_brief_history_trend_status_transition": "PASS->PASS",
        "real_model_supply_pipeline_status_transition": "PASS->PASS",
        "mutation_coverage_matrix_status_transition": "PASS->PASS",
        "status_delta_alert_count": 0,
        "severity_level": "low",
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
    "dataset_promotion_candidate_demo/summary.json": {"bundle_status": "PASS", "decision": "HOLD"},
    "dataset_promotion_candidate_apply_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_promotion_candidate_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_promotion_candidate_apply_history_demo/summary.json": {"bundle_status": "PASS"},
    "dataset_promotion_effectiveness_demo/summary.json": {"bundle_status": "PASS", "effectiveness_decision": "KEEP"},
    "dataset_promotion_effectiveness_history_demo/summary.json": {"bundle_status": "PASS", "trend_status": "PASS"},
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
        "pack_readiness_score": 85.0,
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
        "moat_public_score": 86.0,
        "verdict": "STRONG_MOAT_SIGNAL",
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
        "rare_failure_replay_rate": 1.0
    },
    "dataset_failure_distribution_stability_history_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "history_status": "PASS",
        "total_records": 4,
        "avg_stability_score": 80.0
    },
    "dataset_failure_distribution_stability_history_trend_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "trend_status": "PASS",
        "status_transition": "PASS->PASS"
    },
    "dataset_real_model_supply_pipeline_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "supply_pipeline_status": "PASS",
        "supply_pipeline_score": 84.0,
        "new_models_30d": 2,
        "large_model_candidates_30d": 1,
        "license_blockers": 0
    },
    "dataset_mutation_coverage_matrix_v2_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "matrix_status": "PASS",
        "matrix_coverage_score": 83.0,
        "total_matrix_cells": 12,
        "high_risk_uncovered_cells": 1
    },
    "dataset_real_model_growth_trend_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "growth_trend_status": "PASS",
        "growth_velocity_score": 81.0,
        "trend_band": "accelerating",
        "delta_total_real_models": 2,
        "delta_large_models": 1
    },
    "dataset_model_intake_board_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "board_status": "NEEDS_REVIEW",
        "board_score": 74.0,
        "ready_count": 1,
        "blocked_count": 1,
        "ingested_count": 1
    },
    "dataset_anchor_model_pack_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "pack_status": "PASS",
        "pack_quality_score": 83.0,
        "selected_cases": 3,
        "selected_large_cases": 2
    },
    "dataset_failure_matrix_expansion_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "expansion_status": "NEEDS_REVIEW",
        "expansion_readiness_score": 69.0,
        "planned_expansion_tasks": 2,
        "high_risk_uncovered_cells": 2
    },
    "dataset_model_intake_board_history_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "history_status": "PASS",
        "total_records": 4,
        "avg_board_score": 80.0
    },
    "dataset_model_intake_board_history_trend_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "trend_status": "PASS",
        "status_transition": "PASS->PASS",
        "delta_avg_board_score": 1.0
    },
    "dataset_anchor_model_pack_history_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "history_status": "PASS",
        "total_records": 4,
        "avg_pack_quality_score": 83.0
    },
    "dataset_anchor_model_pack_history_trend_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "trend_status": "PASS",
        "status_transition": "PASS->PASS",
        "delta_avg_pack_quality_score": 0.5
    },
    "dataset_failure_matrix_expansion_history_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "history_status": "PASS",
        "total_records": 4,
        "avg_expansion_readiness_score": 78.0
    },
    "dataset_failure_matrix_expansion_history_trend_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "trend_status": "PASS",
        "status_transition": "PASS->PASS",
        "delta_avg_expansion_readiness_score": 0.4
    },
    "dataset_moat_anchor_brief_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "anchor_brief_status": "PASS",
        "anchor_brief_score": 82.0,
        "recommendation": "PUBLISH"
    },
    "dataset_moat_anchor_brief_history_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "history_status": "PASS",
        "total_records": 4,
        "avg_anchor_brief_score": 79.0
    },
    "dataset_moat_anchor_brief_history_trend_v1_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "trend_status": "PASS",
        "status_transition": "PASS->PASS",
        "recommendation_transition": "PUBLISH->PUBLISH"
    },
    "dataset_moat_evidence_page_v2_demo/demo_summary.json": {
        "bundle_status": "PASS",
        "evidence_status": "PASS",
        "publishable": True,
        "evidence_score": 82.0
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
}
for rel, payload in mapping.items():
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")
PY
else
  bash scripts/demo_dataset_pipeline.sh >/dev/null
  bash scripts/demo_dataset_artifacts_pipeline.sh >/dev/null
  bash scripts/demo_dataset_history.sh >/dev/null
  bash scripts/demo_dataset_governance.sh >/dev/null
  bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null
  bash scripts/demo_dataset_governance_history.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune_apply.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune_apply_history.sh >/dev/null
  bash scripts/demo_dataset_governance_snapshot.sh >/dev/null
  bash scripts/demo_dataset_governance_snapshot_trend.sh >/dev/null
  bash scripts/demo_dataset_failure_taxonomy_coverage.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_benchmark.sh >/dev/null
  bash scripts/demo_dataset_model_scale_ladder.sh >/dev/null
  bash scripts/demo_dataset_failure_policy_patch_advisor.sh >/dev/null
  bash scripts/demo_dataset_blind_spot_backlog.sh >/dev/null
  bash scripts/demo_dataset_policy_patch_replay_evaluator.sh >/dev/null
  bash scripts/demo_dataset_governance_evidence_pack.sh >/dev/null
  bash scripts/demo_dataset_moat_trend_snapshot.sh >/dev/null
  bash scripts/demo_dataset_external_proof_score.sh >/dev/null
  bash scripts/demo_dataset_backlog_execution_bridge.sh >/dev/null
  bash scripts/demo_dataset_replay_quality_guard.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_apply.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_apply_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness_history.sh >/dev/null
  bash scripts/demo_dataset_policy_autotune_history.sh >/dev/null
  bash scripts/demo_dataset_modelica_library_provenance_guard_v1.sh >/dev/null
  bash scripts/demo_dataset_large_model_benchmark_pack_v1.sh >/dev/null
  bash scripts/demo_dataset_mutation_campaign_tracker_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_public_scoreboard_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_license_compliance_gate_v1.sh >/dev/null
  bash scripts/demo_dataset_modelica_mutation_recipe_library_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_failure_yield_tracker_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_intake_backlog_prioritizer_v1.sh >/dev/null
  bash scripts/demo_dataset_modelica_moat_readiness_gate_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_supply_health_v1.sh >/dev/null
  bash scripts/demo_dataset_mutation_recipe_execution_audit_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_intake_portfolio_v1.sh >/dev/null
  bash scripts/demo_dataset_mutation_coverage_depth_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_stability_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_stability_history_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_stability_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_supply_pipeline_v1.sh >/dev/null
  bash scripts/demo_dataset_mutation_coverage_matrix_v2.sh >/dev/null
  bash scripts/demo_dataset_real_model_growth_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_model_intake_board_v1.sh >/dev/null
  bash scripts/demo_dataset_anchor_model_pack_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_matrix_expansion_v1.sh >/dev/null
  bash scripts/demo_dataset_model_intake_board_history_v1.sh >/dev/null
  bash scripts/demo_dataset_model_intake_board_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_anchor_model_pack_history_v1.sh >/dev/null
  bash scripts/demo_dataset_anchor_model_pack_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_matrix_expansion_history_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_matrix_expansion_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_anchor_brief_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_anchor_brief_history_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_anchor_brief_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_evidence_page_v2.sh >/dev/null
  bash scripts/demo_dataset_modelica_release_candidate_gate_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_advisor_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_advisor_history_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_advisor_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_execution_board_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_execution_board_history_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_execution_board_history_trend_v1.sh >/dev/null
fi

python3 -m gateforge.dataset_optional_ci_contract \
  --artifacts-root artifacts \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_optional_ci_contract_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
checks = payload.get("checks", [])
flags = {
    "contract_status_pass": "PASS" if payload.get("status") == "PASS" else "FAIL",
    "required_summary_count_present": "PASS" if int(payload.get("required_summary_count", 0) or 0) >= 10 else "FAIL",
    "checks_non_empty": "PASS" if isinstance(checks, list) and len(checks) > 0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "contract_status": payload.get("status"),
    "required_summary_count": payload.get("required_summary_count"),
    "fail_count": payload.get("fail_count"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Optional CI Contract Demo",
            "",
            f"- contract_status: `{demo['contract_status']}`",
            f"- required_summary_count: `{demo['required_summary_count']}`",
            f"- fail_count: `{demo['fail_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
