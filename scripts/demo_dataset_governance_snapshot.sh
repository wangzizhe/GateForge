#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_snapshot_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ]; then
  mkdir -p artifacts/dataset_pipeline_demo artifacts/dataset_history_demo artifacts/dataset_policy_lifecycle_demo \
    artifacts/dataset_governance_history_demo artifacts/dataset_strategy_autotune_demo \
    artifacts/dataset_strategy_autotune_apply_history_demo artifacts/dataset_promotion_candidate_history_demo \
    artifacts/dataset_promotion_candidate_apply_history_demo artifacts/dataset_promotion_effectiveness_demo \
    artifacts/dataset_promotion_effectiveness_history_demo artifacts/dataset_failure_taxonomy_coverage_demo \
    artifacts/dataset_failure_distribution_benchmark_demo artifacts/dataset_model_scale_ladder_demo \
    artifacts/dataset_failure_policy_patch_advisor_demo artifacts/dataset_modelica_library_provenance_guard_v1_demo \
    artifacts/dataset_large_model_benchmark_pack_v1_demo artifacts/dataset_mutation_campaign_tracker_v1_demo \
    artifacts/dataset_moat_public_scoreboard_v1_demo artifacts/dataset_real_model_license_compliance_gate_v1_demo \
    artifacts/dataset_modelica_mutation_recipe_library_v1_demo artifacts/dataset_real_model_failure_yield_tracker_v1_demo \
    artifacts/dataset_real_model_intake_backlog_prioritizer_v1_demo artifacts/dataset_modelica_moat_readiness_gate_v1_demo \
    artifacts/dataset_real_model_supply_health_v1_demo artifacts/dataset_mutation_recipe_execution_audit_v1_demo \
    artifacts/dataset_modelica_release_candidate_gate_v1_demo artifacts/dataset_intake_growth_advisor_v1_demo \
    artifacts/dataset_intake_growth_advisor_history_v1_demo artifacts/dataset_intake_growth_advisor_history_trend_v1_demo \
    artifacts/dataset_intake_growth_execution_board_v1_demo artifacts/dataset_intake_growth_execution_board_history_v1_demo \
    artifacts/dataset_intake_growth_execution_board_history_trend_v1_demo \
    artifacts/dataset_real_model_intake_portfolio_v1_demo artifacts/dataset_mutation_coverage_depth_v1_demo \
    artifacts/dataset_failure_distribution_stability_v1_demo \
    artifacts/dataset_failure_distribution_stability_history_v1_demo \
    artifacts/dataset_failure_distribution_stability_history_trend_v1_demo \
    artifacts/dataset_moat_anchor_brief_v1_demo artifacts/dataset_moat_anchor_brief_history_v1_demo \
    artifacts/dataset_moat_anchor_brief_history_trend_v1_demo \
    artifacts/dataset_real_model_supply_pipeline_v1_demo artifacts/dataset_mutation_coverage_matrix_v2_demo
  cat > artifacts/dataset_pipeline_demo/summary.json <<'JSON'
{"bundle_status":"PASS","build_deduplicated_cases":12,"quality_failure_case_rate":0.3}
JSON
  cat > artifacts/dataset_history_demo/history_summary.json <<'JSON'
{"total_records":4,"latest_failure_case_rate":0.3}
JSON
  cat > artifacts/dataset_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_policy_lifecycle_demo/ledger_summary.json <<'JSON'
{"latest_status":"PASS","total_records":4}
JSON
  cat > artifacts/dataset_governance_history_demo/trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_policy_lifecycle_demo/effectiveness.json <<'JSON'
{"decision":"KEEP"}
JSON
  cat > artifacts/dataset_strategy_autotune_demo/advisor.json <<'JSON'
{"advice":{"suggested_policy_profile":"dataset_default","suggested_action":"monitor"}}
JSON
  cat > artifacts/dataset_strategy_autotune_apply_history_demo/history_summary.json <<'JSON'
{"latest_final_status":"PASS","fail_rate":0.0,"needs_review_rate":0.1}
JSON
  cat > artifacts/dataset_strategy_autotune_apply_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_promotion_candidate_history_demo/history_summary.json <<'JSON'
{"latest_decision":"HOLD","hold_rate":0.5,"block_rate":0.0}
JSON
  cat > artifacts/dataset_promotion_candidate_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json <<'JSON'
{"latest_final_status":"PASS","fail_rate":0.0,"needs_review_rate":0.1}
JSON
  cat > artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_promotion_effectiveness_demo/effectiveness.json <<'JSON'
{"decision":"KEEP"}
JSON
  cat > artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json <<'JSON'
{"latest_decision":"KEEP","rollback_review_rate":0.0}
JSON
  cat > artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_failure_taxonomy_coverage_demo/summary.json <<'JSON'
{"status":"PASS","total_cases":12,"unique_failure_type_count":5,"missing_failure_types":[],"missing_model_scales":[],"missing_stages":[]}
JSON
  cat > artifacts/dataset_failure_distribution_benchmark_demo/summary.json <<'JSON'
{"status":"PASS","detection_rate_after":0.92,"false_positive_rate_after":0.03,"regression_rate_after":0.08,"distribution_drift_score":0.18}
JSON
  cat > artifacts/dataset_model_scale_ladder_demo/summary.json <<'JSON'
{"status":"PASS","medium_ready":true,"large_ready":true,"scale_counts":{"small":5,"medium":3,"large":2},"ci_recommendation":{"main":["small_smoke","medium_smoke"],"optional":["medium_full","large_subset"]}}
JSON
  cat > artifacts/dataset_failure_policy_patch_advisor_demo/advisor.json <<'JSON'
{"status":"PASS","advice":{"suggested_action":"keep","suggested_policy_profile":"dataset_default","confidence":0.64,"reasons":["signals_stable"]}}
JSON
  cat > artifacts/dataset_modelica_library_provenance_guard_v1_demo/summary.json <<'JSON'
{"status":"PASS","provenance_completeness_pct":99.0,"unknown_license_ratio_pct":0.0}
JSON
  cat > artifacts/dataset_large_model_benchmark_pack_v1_demo/summary.json <<'JSON'
{"status":"PASS","pack_readiness_score":86.0,"selected_large_models":3,"selected_large_mutations":8}
JSON
  cat > artifacts/dataset_mutation_campaign_tracker_v1_demo/summary.json <<'JSON'
{"status":"PASS","completion_ratio_pct":88.0,"campaign_phase":"scale_out"}
JSON
  cat > artifacts/dataset_moat_public_scoreboard_v1_demo/summary.json <<'JSON'
{"status":"PASS","moat_public_score":84.0,"verdict":"STRONG_MOAT_SIGNAL"}
JSON
  cat > artifacts/dataset_real_model_license_compliance_gate_v1_demo/summary.json <<'JSON'
{"status":"PASS","unknown_license_ratio_pct":0.0,"disallowed_license_count":0}
JSON
  cat > artifacts/dataset_modelica_mutation_recipe_library_v1_demo/summary.json <<'JSON'
{"status":"PASS","total_recipes":10,"high_priority_recipes":2}
JSON
  cat > artifacts/dataset_real_model_failure_yield_tracker_v1_demo/summary.json <<'JSON'
{"status":"PASS","yield_per_accepted_model":1.8,"matrix_execution_ratio_pct":88.0}
JSON
  cat > artifacts/dataset_real_model_intake_backlog_prioritizer_v1_demo/summary.json <<'JSON'
{"status":"PASS","backlog_item_count":3,"p0_count":0}
JSON
  cat > artifacts/dataset_modelica_moat_readiness_gate_v1_demo/summary.json <<'JSON'
{"status":"PASS","moat_readiness_score":83.0,"release_recommendation":"GO"}
JSON
  cat > artifacts/dataset_real_model_supply_health_v1_demo/summary.json <<'JSON'
{"status":"PASS","supply_health_score":84.0,"supply_gap_count":0}
JSON
  cat > artifacts/dataset_mutation_recipe_execution_audit_v1_demo/summary.json <<'JSON'
{"status":"PASS","execution_coverage_pct":81.0,"missing_recipe_count":1}
JSON
  cat > artifacts/dataset_modelica_release_candidate_gate_v1_demo/summary.json <<'JSON'
{"status":"PASS","release_candidate_score":84.0,"candidate_decision":"GO"}
JSON
  cat > artifacts/dataset_intake_growth_advisor_v1_demo/summary.json <<'JSON'
{"status":"PASS","advice":{"suggested_action":"keep","backlog_actions":[]}}
JSON
  cat > artifacts/dataset_intake_growth_advisor_history_v1_demo/summary.json <<'JSON'
{"status":"PASS","latest_suggested_action":"keep","recovery_plan_rate":0.0}
JSON
  cat > artifacts/dataset_intake_growth_advisor_history_trend_v1_demo/summary.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_intake_growth_execution_board_v1_demo/summary.json <<'JSON'
{"status":"PASS","execution_score":84.0,"critical_open_tasks":0,"projected_weeks_to_target":0}
JSON
  cat > artifacts/dataset_intake_growth_execution_board_history_v1_demo/summary.json <<'JSON'
{"status":"PASS","avg_execution_score":82.0,"critical_open_tasks_rate":0.0}
JSON
  cat > artifacts/dataset_intake_growth_execution_board_history_trend_v1_demo/summary.json <<'JSON'
{"status":"PASS","trend":{"alerts":[]}}
JSON
  cat > artifacts/dataset_real_model_intake_portfolio_v1_demo/summary.json <<'JSON'
{"status":"PASS","total_real_models":4,"large_models":1,"license_clean_ratio_pct":100.0,"active_domains_count":3}
JSON
  cat > artifacts/dataset_mutation_coverage_depth_v1_demo/summary.json <<'JSON'
{"status":"PASS","coverage_depth_score":91.0,"uncovered_cells_count":1,"high_risk_gaps_count":0}
JSON
  cat > artifacts/dataset_failure_distribution_stability_v1_demo/summary.json <<'JSON'
{"status":"PASS","stability_score":83.0,"drift_band":"low","rare_failure_replay_rate":1.0,"delta_distribution_drift_score":0.01}
JSON
  cat > artifacts/dataset_failure_distribution_stability_history_v1_demo/summary.json <<'JSON'
{"status":"PASS","total_records":4,"avg_stability_score":80.0,"avg_rare_failure_replay_rate":0.85}
JSON
  cat > artifacts/dataset_failure_distribution_stability_history_trend_v1_demo/summary.json <<'JSON'
{"status":"PASS","trend":{"status_transition":"PASS->PASS","delta_avg_stability_score":1.0,"delta_avg_distribution_drift_score":-0.01,"delta_avg_rare_failure_replay_rate":0.05}}
JSON
  cat > artifacts/dataset_moat_anchor_brief_v1_demo/summary.json <<'JSON'
{"status":"PASS","anchor_brief_score":82.0,"recommendation":"PUBLISH","confidence_band":"high"}
JSON
  cat > artifacts/dataset_moat_anchor_brief_history_v1_demo/summary.json <<'JSON'
{"status":"PASS","total_records":4,"publish_rate":0.75,"latest_recommendation":"PUBLISH"}
JSON
  cat > artifacts/dataset_moat_anchor_brief_history_trend_v1_demo/summary.json <<'JSON'
{"status":"PASS","trend":{"status_transition":"PASS->PASS","recommendation_transition":"PUBLISH->PUBLISH","delta_avg_anchor_brief_score":1.2,"delta_publish_rate":0.05}}
JSON
  cat > artifacts/dataset_real_model_supply_pipeline_v1_demo/summary.json <<'JSON'
{"status":"PASS","supply_pipeline_score":84.0,"new_models_30d":2,"large_model_candidates_30d":1,"license_blockers":0}
JSON
  cat > artifacts/dataset_mutation_coverage_matrix_v2_demo/summary.json <<'JSON'
{"status":"PASS","matrix_coverage_score":83.0,"total_matrix_cells":12,"high_risk_uncovered_cells":1}
JSON
else
  bash scripts/demo_dataset_pipeline.sh >/dev/null
  bash scripts/demo_dataset_history.sh >/dev/null
  if [ ! -f artifacts/dataset_history_demo/history_summary.json ]; then
    bash scripts/demo_dataset_history.sh >/dev/null
  fi
  if [ ! -f artifacts/dataset_history_demo/history_summary.json ]; then
    echo "missing artifacts/dataset_history_demo/history_summary.json" >&2
    exit 1
  fi
  bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null
  bash scripts/demo_dataset_governance_history.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune.sh >/dev/null
  bash scripts/demo_dataset_strategy_autotune_apply_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_candidate_apply_history.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness.sh >/dev/null
  bash scripts/demo_dataset_promotion_effectiveness_history.sh >/dev/null
  bash scripts/demo_dataset_failure_taxonomy_coverage.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_benchmark.sh >/dev/null
  bash scripts/demo_dataset_model_scale_ladder.sh >/dev/null
  bash scripts/demo_dataset_failure_policy_patch_advisor.sh >/dev/null
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
  bash scripts/demo_dataset_modelica_release_candidate_gate_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_advisor_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_advisor_history_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_advisor_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_execution_board_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_execution_board_history_v1.sh >/dev/null
  bash scripts/demo_dataset_intake_growth_execution_board_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_intake_portfolio_v1.sh >/dev/null
  bash scripts/demo_dataset_mutation_coverage_depth_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_stability_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_stability_history_v1.sh >/dev/null
  bash scripts/demo_dataset_failure_distribution_stability_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_anchor_brief_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_anchor_brief_history_v1.sh >/dev/null
  bash scripts/demo_dataset_moat_anchor_brief_history_trend_v1.sh >/dev/null
  bash scripts/demo_dataset_real_model_supply_pipeline_v1.sh >/dev/null
  bash scripts/demo_dataset_mutation_coverage_matrix_v2.sh >/dev/null
fi

ARGS=(
  --dataset-pipeline-summary artifacts/dataset_pipeline_demo/summary.json
  --dataset-history-summary artifacts/dataset_history_demo/history_summary.json
  --dataset-history-trend artifacts/dataset_history_demo/history_trend.json
  --dataset-governance-summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json
  --dataset-governance-trend artifacts/dataset_governance_history_demo/trend.json
  --dataset-policy-effectiveness artifacts/dataset_policy_lifecycle_demo/effectiveness.json
  --dataset-strategy-advisor artifacts/dataset_strategy_autotune_demo/advisor.json
  --dataset-strategy-apply-history artifacts/dataset_strategy_autotune_apply_history_demo/history_summary.json
  --dataset-strategy-apply-history-trend artifacts/dataset_strategy_autotune_apply_history_demo/history_trend.json
)

if [ -f artifacts/dataset_promotion_candidate_history_demo/history_summary.json ] && [ -f artifacts/dataset_promotion_candidate_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-history artifacts/dataset_promotion_candidate_history_demo/history_summary.json)
  ARGS+=(--dataset-promotion-history-trend artifacts/dataset_promotion_candidate_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json ] && [ -f artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-apply-history artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json)
  ARGS+=(--dataset-promotion-apply-history-trend artifacts/dataset_promotion_candidate_apply_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_demo/effectiveness.json ]; then
  ARGS+=(--dataset-promotion-effectiveness artifacts/dataset_promotion_effectiveness_demo/effectiveness.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json ]; then
  ARGS+=(--dataset-promotion-effectiveness-history artifacts/dataset_promotion_effectiveness_history_demo/history_summary.json)
fi
if [ -f artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json ]; then
  ARGS+=(--dataset-promotion-effectiveness-history-trend artifacts/dataset_promotion_effectiveness_history_demo/history_trend.json)
fi
if [ -f artifacts/dataset_failure_taxonomy_coverage_demo/summary.json ]; then
  ARGS+=(--dataset-failure-taxonomy-coverage artifacts/dataset_failure_taxonomy_coverage_demo/summary.json)
fi
if [ -f artifacts/dataset_failure_distribution_benchmark_demo/summary.json ]; then
  ARGS+=(--dataset-failure-distribution-benchmark artifacts/dataset_failure_distribution_benchmark_demo/summary.json)
fi
if [ -f artifacts/dataset_model_scale_ladder_demo/summary.json ]; then
  ARGS+=(--dataset-model-scale-ladder artifacts/dataset_model_scale_ladder_demo/summary.json)
fi
if [ -f artifacts/dataset_failure_policy_patch_advisor_demo/advisor.json ]; then
  ARGS+=(--dataset-failure-policy-patch-advisor artifacts/dataset_failure_policy_patch_advisor_demo/advisor.json)
fi
if [ -f artifacts/dataset_modelica_library_provenance_guard_v1_demo/summary.json ]; then
  ARGS+=(--dataset-modelica-library-provenance-guard artifacts/dataset_modelica_library_provenance_guard_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_large_model_benchmark_pack_v1_demo/summary.json ]; then
  ARGS+=(--dataset-large-model-benchmark-pack artifacts/dataset_large_model_benchmark_pack_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_mutation_campaign_tracker_v1_demo/summary.json ]; then
  ARGS+=(--dataset-mutation-campaign-tracker artifacts/dataset_mutation_campaign_tracker_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_moat_public_scoreboard_v1_demo/summary.json ]; then
  ARGS+=(--dataset-moat-public-scoreboard artifacts/dataset_moat_public_scoreboard_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_real_model_license_compliance_gate_v1_demo/summary.json ]; then
  ARGS+=(--dataset-real-model-license-compliance artifacts/dataset_real_model_license_compliance_gate_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_modelica_mutation_recipe_library_v1_demo/summary.json ]; then
  ARGS+=(--dataset-modelica-mutation-recipe-library artifacts/dataset_modelica_mutation_recipe_library_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_real_model_failure_yield_tracker_v1_demo/summary.json ]; then
  ARGS+=(--dataset-real-model-failure-yield artifacts/dataset_real_model_failure_yield_tracker_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_real_model_intake_backlog_prioritizer_v1_demo/summary.json ]; then
  ARGS+=(--dataset-real-model-intake-backlog artifacts/dataset_real_model_intake_backlog_prioritizer_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_modelica_moat_readiness_gate_v1_demo/summary.json ]; then
  ARGS+=(--dataset-modelica-moat-readiness-gate artifacts/dataset_modelica_moat_readiness_gate_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_real_model_supply_health_v1_demo/summary.json ]; then
  ARGS+=(--dataset-real-model-supply-health artifacts/dataset_real_model_supply_health_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_mutation_recipe_execution_audit_v1_demo/summary.json ]; then
  ARGS+=(--dataset-mutation-recipe-execution-audit artifacts/dataset_mutation_recipe_execution_audit_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_modelica_release_candidate_gate_v1_demo/summary.json ]; then
  ARGS+=(--dataset-modelica-release-candidate-gate artifacts/dataset_modelica_release_candidate_gate_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_intake_growth_advisor_v1_demo/summary.json ]; then
  ARGS+=(--dataset-intake-growth-advisor artifacts/dataset_intake_growth_advisor_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_intake_growth_advisor_history_v1_demo/summary.json ]; then
  ARGS+=(--dataset-intake-growth-advisor-history artifacts/dataset_intake_growth_advisor_history_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_intake_growth_advisor_history_trend_v1_demo/summary.json ]; then
  ARGS+=(--dataset-intake-growth-advisor-history-trend artifacts/dataset_intake_growth_advisor_history_trend_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_intake_growth_execution_board_v1_demo/summary.json ]; then
  ARGS+=(--dataset-intake-growth-execution-board artifacts/dataset_intake_growth_execution_board_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_intake_growth_execution_board_history_v1_demo/summary.json ]; then
  ARGS+=(--dataset-intake-growth-execution-board-history artifacts/dataset_intake_growth_execution_board_history_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_intake_growth_execution_board_history_trend_v1_demo/summary.json ]; then
  ARGS+=(--dataset-intake-growth-execution-board-history-trend artifacts/dataset_intake_growth_execution_board_history_trend_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_real_model_intake_portfolio_v1_demo/summary.json ]; then
  ARGS+=(--dataset-real-model-intake-portfolio artifacts/dataset_real_model_intake_portfolio_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_mutation_coverage_depth_v1_demo/summary.json ]; then
  ARGS+=(--dataset-mutation-coverage-depth artifacts/dataset_mutation_coverage_depth_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_failure_distribution_stability_v1_demo/summary.json ]; then
  ARGS+=(--dataset-failure-distribution-stability artifacts/dataset_failure_distribution_stability_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_failure_distribution_stability_history_v1_demo/summary.json ]; then
  ARGS+=(--dataset-failure-distribution-stability-history artifacts/dataset_failure_distribution_stability_history_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_failure_distribution_stability_history_trend_v1_demo/summary.json ]; then
  ARGS+=(--dataset-failure-distribution-stability-history-trend artifacts/dataset_failure_distribution_stability_history_trend_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_moat_anchor_brief_v1_demo/summary.json ]; then
  ARGS+=(--dataset-moat-anchor-brief artifacts/dataset_moat_anchor_brief_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_moat_anchor_brief_history_v1_demo/summary.json ]; then
  ARGS+=(--dataset-moat-anchor-brief-history artifacts/dataset_moat_anchor_brief_history_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_moat_anchor_brief_history_trend_v1_demo/summary.json ]; then
  ARGS+=(--dataset-moat-anchor-brief-history-trend artifacts/dataset_moat_anchor_brief_history_trend_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_real_model_supply_pipeline_v1_demo/summary.json ]; then
  ARGS+=(--dataset-real-model-supply-pipeline artifacts/dataset_real_model_supply_pipeline_v1_demo/summary.json)
fi
if [ -f artifacts/dataset_mutation_coverage_matrix_v2_demo/summary.json ]; then
  ARGS+=(--dataset-mutation-coverage-matrix artifacts/dataset_mutation_coverage_matrix_v2_demo/summary.json)
fi

python3 -m gateforge.dataset_governance_snapshot \
  "${ARGS[@]}" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_snapshot_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if payload.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "kpis_present": "PASS" if isinstance(payload.get("kpis"), dict) else "FAIL",
    "risks_present": "PASS" if isinstance(payload.get("risks"), list) else "FAIL",
    "promotion_effectiveness_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_promotion_effectiveness_history_trend_status"), (str, type(None)))
    else "FAIL",
    "failure_taxonomy_coverage_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_taxonomy_coverage_status"), (str, type(None)))
    else "FAIL",
    "failure_distribution_benchmark_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_distribution_benchmark_status"), (str, type(None)))
    else "FAIL",
    "model_scale_ladder_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_model_scale_ladder_status"), (str, type(None)))
    else "FAIL",
    "failure_policy_patch_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_policy_patch_advisor_status"), (str, type(None)))
    else "FAIL",
    "modelica_library_provenance_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_modelica_library_provenance_guard_status"), (str, type(None)))
    else "FAIL",
    "large_model_benchmark_pack_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_large_model_benchmark_pack_status"), (str, type(None)))
    else "FAIL",
    "mutation_campaign_tracker_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_mutation_campaign_tracker_status"), (str, type(None)))
    else "FAIL",
    "moat_public_scoreboard_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_moat_public_scoreboard_status"), (str, type(None)))
    else "FAIL",
    "real_model_license_compliance_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_real_model_license_compliance_status"), (str, type(None)))
    else "FAIL",
    "modelica_mutation_recipe_library_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_modelica_mutation_recipe_library_status"), (str, type(None)))
    else "FAIL",
    "real_model_failure_yield_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_real_model_failure_yield_status"), (str, type(None)))
    else "FAIL",
    "real_model_intake_backlog_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_real_model_intake_backlog_status"), (str, type(None)))
    else "FAIL",
    "modelica_moat_readiness_gate_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_modelica_moat_readiness_gate_status"), (str, type(None)))
    else "FAIL",
    "real_model_supply_health_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_real_model_supply_health_status"), (str, type(None)))
    else "FAIL",
    "mutation_recipe_execution_audit_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_mutation_recipe_execution_audit_status"), (str, type(None)))
    else "FAIL",
    "modelica_release_candidate_gate_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_modelica_release_candidate_gate_status"), (str, type(None)))
    else "FAIL",
    "intake_growth_advisor_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_intake_growth_advisor_status"), (str, type(None)))
    else "FAIL",
    "intake_growth_advisor_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_intake_growth_advisor_history_status"), (str, type(None)))
    else "FAIL",
    "intake_growth_advisor_history_trend_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_intake_growth_advisor_history_trend_status"), (str, type(None)))
    else "FAIL",
    "intake_growth_execution_board_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_status"), (str, type(None)))
    else "FAIL",
    "intake_growth_execution_board_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_history_status"), (str, type(None)))
    else "FAIL",
    "intake_growth_execution_board_history_trend_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_history_trend_status"), (str, type(None)))
    else "FAIL",
    "real_model_intake_portfolio_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_real_model_intake_portfolio_status"), (str, type(None)))
    else "FAIL",
    "mutation_coverage_depth_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_mutation_coverage_depth_status"), (str, type(None)))
    else "FAIL",
    "failure_distribution_stability_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_distribution_stability_status"), (str, type(None)))
    else "FAIL",
    "failure_distribution_stability_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_distribution_stability_history_status"), (str, type(None)))
    else "FAIL",
    "failure_distribution_stability_history_trend_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_failure_distribution_stability_history_trend_status"), (str, type(None)))
    else "FAIL",
    "moat_anchor_brief_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_moat_anchor_brief_status"), (str, type(None)))
    else "FAIL",
    "moat_anchor_brief_history_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_moat_anchor_brief_history_status"), (str, type(None)))
    else "FAIL",
    "moat_anchor_brief_history_trend_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_moat_anchor_brief_history_trend_status"), (str, type(None)))
    else "FAIL",
    "real_model_supply_pipeline_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_real_model_supply_pipeline_status"), (str, type(None)))
    else "FAIL",
    "mutation_coverage_matrix_kpi_present": "PASS"
    if isinstance((payload.get("kpis") or {}).get("dataset_mutation_coverage_matrix_status"), (str, type(None)))
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "status": payload.get("status"),
    "risks_count": len(payload.get("risks") or []),
    "promotion_effectiveness_history_trend_status": (payload.get("kpis") or {}).get(
        "dataset_promotion_effectiveness_history_trend_status"
    ),
    "promotion_effectiveness_history_latest_decision": (payload.get("kpis") or {}).get(
        "dataset_promotion_effectiveness_history_latest_decision"
    ),
    "failure_taxonomy_coverage_status": (payload.get("kpis") or {}).get("dataset_failure_taxonomy_coverage_status"),
    "failure_taxonomy_missing_model_scales_count": (payload.get("kpis") or {}).get(
        "dataset_failure_taxonomy_missing_model_scales_count"
    ),
    "failure_distribution_benchmark_status": (payload.get("kpis") or {}).get(
        "dataset_failure_distribution_benchmark_status"
    ),
    "failure_distribution_drift_score": (payload.get("kpis") or {}).get(
        "dataset_failure_distribution_drift_score"
    ),
    "model_scale_ladder_status": (payload.get("kpis") or {}).get("dataset_model_scale_ladder_status"),
    "model_scale_large_ready": (payload.get("kpis") or {}).get("dataset_model_scale_large_ready"),
    "failure_policy_patch_advisor_status": (payload.get("kpis") or {}).get("dataset_failure_policy_patch_advisor_status"),
    "failure_policy_patch_suggested_action": (payload.get("kpis") or {}).get("dataset_failure_policy_patch_suggested_action"),
    "modelica_library_provenance_guard_status": (payload.get("kpis") or {}).get("dataset_modelica_library_provenance_guard_status"),
    "modelica_library_provenance_completeness_pct": (payload.get("kpis") or {}).get("dataset_modelica_library_provenance_completeness_pct"),
    "large_model_benchmark_pack_status": (payload.get("kpis") or {}).get("dataset_large_model_benchmark_pack_status"),
    "large_model_benchmark_pack_readiness_score": (payload.get("kpis") or {}).get("dataset_large_model_benchmark_pack_readiness_score"),
    "mutation_campaign_tracker_status": (payload.get("kpis") or {}).get("dataset_mutation_campaign_tracker_status"),
    "mutation_campaign_completion_ratio_pct": (payload.get("kpis") or {}).get("dataset_mutation_campaign_completion_ratio_pct"),
    "moat_public_scoreboard_status": (payload.get("kpis") or {}).get("dataset_moat_public_scoreboard_status"),
    "moat_public_score": (payload.get("kpis") or {}).get("dataset_moat_public_score"),
    "real_model_license_compliance_status": (payload.get("kpis") or {}).get("dataset_real_model_license_compliance_status"),
    "real_model_license_compliance_unknown_license_ratio_pct": (payload.get("kpis") or {}).get(
        "dataset_real_model_license_compliance_unknown_license_ratio_pct"
    ),
    "modelica_mutation_recipe_library_status": (payload.get("kpis") or {}).get(
        "dataset_modelica_mutation_recipe_library_status"
    ),
    "modelica_mutation_recipe_total": (payload.get("kpis") or {}).get("dataset_modelica_mutation_recipe_total"),
    "real_model_failure_yield_status": (payload.get("kpis") or {}).get("dataset_real_model_failure_yield_status"),
    "real_model_failure_yield_per_accepted_model": (payload.get("kpis") or {}).get(
        "dataset_real_model_failure_yield_per_accepted_model"
    ),
    "real_model_intake_backlog_status": (payload.get("kpis") or {}).get("dataset_real_model_intake_backlog_status"),
    "real_model_intake_backlog_p0_count": (payload.get("kpis") or {}).get("dataset_real_model_intake_backlog_p0_count"),
    "modelica_moat_readiness_gate_status": (payload.get("kpis") or {}).get(
        "dataset_modelica_moat_readiness_gate_status"
    ),
    "modelica_moat_readiness_score": (payload.get("kpis") or {}).get("dataset_modelica_moat_readiness_score"),
    "real_model_supply_health_status": (payload.get("kpis") or {}).get("dataset_real_model_supply_health_status"),
    "real_model_supply_health_score": (payload.get("kpis") or {}).get("dataset_real_model_supply_health_score"),
    "mutation_recipe_execution_audit_status": (payload.get("kpis") or {}).get("dataset_mutation_recipe_execution_audit_status"),
    "mutation_recipe_execution_coverage_pct": (payload.get("kpis") or {}).get(
        "dataset_mutation_recipe_execution_coverage_pct"
    ),
    "modelica_release_candidate_gate_status": (payload.get("kpis") or {}).get("dataset_modelica_release_candidate_gate_status"),
    "modelica_release_candidate_score": (payload.get("kpis") or {}).get("dataset_modelica_release_candidate_score"),
    "intake_growth_advisor_status": (payload.get("kpis") or {}).get("dataset_intake_growth_advisor_status"),
    "intake_growth_suggested_action": (payload.get("kpis") or {}).get("dataset_intake_growth_suggested_action"),
    "intake_growth_backlog_action_count": (payload.get("kpis") or {}).get("dataset_intake_growth_backlog_action_count"),
    "intake_growth_advisor_history_status": (payload.get("kpis") or {}).get("dataset_intake_growth_advisor_history_status"),
    "intake_growth_advisor_history_trend_status": (payload.get("kpis") or {}).get("dataset_intake_growth_advisor_history_trend_status"),
    "intake_growth_execution_board_status": (payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_status"),
    "intake_growth_execution_board_execution_score": (payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_execution_score"),
    "intake_growth_execution_board_history_status": (payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_history_status"),
    "intake_growth_execution_board_history_trend_status": (payload.get("kpis") or {}).get("dataset_intake_growth_execution_board_history_trend_status"),
    "real_model_intake_portfolio_status": (payload.get("kpis") or {}).get("dataset_real_model_intake_portfolio_status"),
    "real_model_intake_portfolio_total_real_models": (payload.get("kpis") or {}).get("dataset_real_model_intake_portfolio_total_real_models"),
    "real_model_intake_portfolio_large_models": (payload.get("kpis") or {}).get("dataset_real_model_intake_portfolio_large_models"),
    "mutation_coverage_depth_status": (payload.get("kpis") or {}).get("dataset_mutation_coverage_depth_status"),
    "mutation_coverage_depth_score": (payload.get("kpis") or {}).get("dataset_mutation_coverage_depth_score"),
    "failure_distribution_stability_status": (payload.get("kpis") or {}).get("dataset_failure_distribution_stability_status"),
    "failure_distribution_stability_score": (payload.get("kpis") or {}).get("dataset_failure_distribution_stability_score"),
    "failure_distribution_stability_rare_failure_replay_rate": (payload.get("kpis") or {}).get("dataset_failure_distribution_stability_rare_failure_replay_rate"),
    "failure_distribution_stability_history_status": (payload.get("kpis") or {}).get("dataset_failure_distribution_stability_history_status"),
    "failure_distribution_stability_history_avg_stability_score": (payload.get("kpis") or {}).get("dataset_failure_distribution_stability_history_avg_stability_score"),
    "failure_distribution_stability_history_trend_status": (payload.get("kpis") or {}).get("dataset_failure_distribution_stability_history_trend_status"),
    "moat_anchor_brief_status": (payload.get("kpis") or {}).get("dataset_moat_anchor_brief_status"),
    "moat_anchor_brief_score": (payload.get("kpis") or {}).get("dataset_moat_anchor_brief_score"),
    "moat_anchor_brief_recommendation": (payload.get("kpis") or {}).get("dataset_moat_anchor_brief_recommendation"),
    "moat_anchor_brief_history_status": (payload.get("kpis") or {}).get("dataset_moat_anchor_brief_history_status"),
    "moat_anchor_brief_history_publish_rate": (payload.get("kpis") or {}).get("dataset_moat_anchor_brief_history_publish_rate"),
    "moat_anchor_brief_history_trend_status": (payload.get("kpis") or {}).get("dataset_moat_anchor_brief_history_trend_status"),
    "real_model_supply_pipeline_status": (payload.get("kpis") or {}).get("dataset_real_model_supply_pipeline_status"),
    "real_model_supply_pipeline_score": (payload.get("kpis") or {}).get("dataset_real_model_supply_pipeline_score"),
    "real_model_supply_pipeline_new_models_30d": (payload.get("kpis") or {}).get("dataset_real_model_supply_pipeline_new_models_30d"),
    "mutation_coverage_matrix_status": (payload.get("kpis") or {}).get("dataset_mutation_coverage_matrix_status"),
    "mutation_coverage_matrix_score": (payload.get("kpis") or {}).get("dataset_mutation_coverage_matrix_score"),
    "mutation_coverage_matrix_high_risk_uncovered_cells": (payload.get("kpis") or {}).get("dataset_mutation_coverage_matrix_high_risk_uncovered_cells"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Snapshot Demo",
            "",
            f"- status: `{summary['status']}`",
            f"- risks_count: `{summary['risks_count']}`",
            f"- promotion_effectiveness_history_trend_status: `{summary['promotion_effectiveness_history_trend_status']}`",
            f"- promotion_effectiveness_history_latest_decision: `{summary['promotion_effectiveness_history_latest_decision']}`",
            f"- failure_taxonomy_coverage_status: `{summary['failure_taxonomy_coverage_status']}`",
            f"- failure_taxonomy_missing_model_scales_count: `{summary['failure_taxonomy_missing_model_scales_count']}`",
            f"- failure_distribution_benchmark_status: `{summary['failure_distribution_benchmark_status']}`",
            f"- failure_distribution_drift_score: `{summary['failure_distribution_drift_score']}`",
            f"- model_scale_ladder_status: `{summary['model_scale_ladder_status']}`",
            f"- model_scale_large_ready: `{summary['model_scale_large_ready']}`",
            f"- failure_policy_patch_advisor_status: `{summary['failure_policy_patch_advisor_status']}`",
            f"- failure_policy_patch_suggested_action: `{summary['failure_policy_patch_suggested_action']}`",
            f"- modelica_library_provenance_guard_status: `{summary['modelica_library_provenance_guard_status']}`",
            f"- modelica_library_provenance_completeness_pct: `{summary['modelica_library_provenance_completeness_pct']}`",
            f"- large_model_benchmark_pack_status: `{summary['large_model_benchmark_pack_status']}`",
            f"- large_model_benchmark_pack_readiness_score: `{summary['large_model_benchmark_pack_readiness_score']}`",
            f"- mutation_campaign_tracker_status: `{summary['mutation_campaign_tracker_status']}`",
            f"- mutation_campaign_completion_ratio_pct: `{summary['mutation_campaign_completion_ratio_pct']}`",
            f"- moat_public_scoreboard_status: `{summary['moat_public_scoreboard_status']}`",
            f"- moat_public_score: `{summary['moat_public_score']}`",
            f"- real_model_license_compliance_status: `{summary['real_model_license_compliance_status']}`",
            f"- real_model_license_compliance_unknown_license_ratio_pct: `{summary['real_model_license_compliance_unknown_license_ratio_pct']}`",
            f"- modelica_mutation_recipe_library_status: `{summary['modelica_mutation_recipe_library_status']}`",
            f"- modelica_mutation_recipe_total: `{summary['modelica_mutation_recipe_total']}`",
            f"- real_model_failure_yield_status: `{summary['real_model_failure_yield_status']}`",
            f"- real_model_failure_yield_per_accepted_model: `{summary['real_model_failure_yield_per_accepted_model']}`",
            f"- real_model_intake_backlog_status: `{summary['real_model_intake_backlog_status']}`",
            f"- real_model_intake_backlog_p0_count: `{summary['real_model_intake_backlog_p0_count']}`",
            f"- modelica_moat_readiness_gate_status: `{summary['modelica_moat_readiness_gate_status']}`",
            f"- modelica_moat_readiness_score: `{summary['modelica_moat_readiness_score']}`",
            f"- real_model_supply_health_status: `{summary['real_model_supply_health_status']}`",
            f"- real_model_supply_health_score: `{summary['real_model_supply_health_score']}`",
            f"- mutation_recipe_execution_audit_status: `{summary['mutation_recipe_execution_audit_status']}`",
            f"- mutation_recipe_execution_coverage_pct: `{summary['mutation_recipe_execution_coverage_pct']}`",
            f"- modelica_release_candidate_gate_status: `{summary['modelica_release_candidate_gate_status']}`",
            f"- modelica_release_candidate_score: `{summary['modelica_release_candidate_score']}`",
            f"- intake_growth_advisor_status: `{summary['intake_growth_advisor_status']}`",
            f"- intake_growth_suggested_action: `{summary['intake_growth_suggested_action']}`",
            f"- intake_growth_backlog_action_count: `{summary['intake_growth_backlog_action_count']}`",
            f"- intake_growth_advisor_history_status: `{summary['intake_growth_advisor_history_status']}`",
            f"- intake_growth_advisor_history_trend_status: `{summary['intake_growth_advisor_history_trend_status']}`",
            f"- intake_growth_execution_board_status: `{summary['intake_growth_execution_board_status']}`",
            f"- intake_growth_execution_board_execution_score: `{summary['intake_growth_execution_board_execution_score']}`",
            f"- intake_growth_execution_board_history_status: `{summary['intake_growth_execution_board_history_status']}`",
            f"- intake_growth_execution_board_history_trend_status: `{summary['intake_growth_execution_board_history_trend_status']}`",
            f"- real_model_intake_portfolio_status: `{summary['real_model_intake_portfolio_status']}`",
            f"- real_model_intake_portfolio_total_real_models: `{summary['real_model_intake_portfolio_total_real_models']}`",
            f"- real_model_intake_portfolio_large_models: `{summary['real_model_intake_portfolio_large_models']}`",
            f"- mutation_coverage_depth_status: `{summary['mutation_coverage_depth_status']}`",
            f"- mutation_coverage_depth_score: `{summary['mutation_coverage_depth_score']}`",
            f"- failure_distribution_stability_status: `{summary['failure_distribution_stability_status']}`",
            f"- failure_distribution_stability_score: `{summary['failure_distribution_stability_score']}`",
            f"- failure_distribution_stability_rare_failure_replay_rate: `{summary['failure_distribution_stability_rare_failure_replay_rate']}`",
            f"- failure_distribution_stability_history_status: `{summary['failure_distribution_stability_history_status']}`",
            f"- failure_distribution_stability_history_avg_stability_score: `{summary['failure_distribution_stability_history_avg_stability_score']}`",
            f"- failure_distribution_stability_history_trend_status: `{summary['failure_distribution_stability_history_trend_status']}`",
            f"- moat_anchor_brief_status: `{summary['moat_anchor_brief_status']}`",
            f"- moat_anchor_brief_score: `{summary['moat_anchor_brief_score']}`",
            f"- moat_anchor_brief_recommendation: `{summary['moat_anchor_brief_recommendation']}`",
            f"- moat_anchor_brief_history_status: `{summary['moat_anchor_brief_history_status']}`",
            f"- moat_anchor_brief_history_publish_rate: `{summary['moat_anchor_brief_history_publish_rate']}`",
            f"- moat_anchor_brief_history_trend_status: `{summary['moat_anchor_brief_history_trend_status']}`",
            f"- real_model_supply_pipeline_status: `{summary['real_model_supply_pipeline_status']}`",
            f"- real_model_supply_pipeline_score: `{summary['real_model_supply_pipeline_score']}`",
            f"- real_model_supply_pipeline_new_models_30d: `{summary['real_model_supply_pipeline_new_models_30d']}`",
            f"- mutation_coverage_matrix_status: `{summary['mutation_coverage_matrix_status']}`",
            f"- mutation_coverage_matrix_score: `{summary['mutation_coverage_matrix_score']}`",
            f"- mutation_coverage_matrix_high_risk_uncovered_cells: `{summary['mutation_coverage_matrix_high_risk_uncovered_cells']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "status": summary["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/demo_summary.json"
cat "$OUT_DIR/demo_summary.md"
