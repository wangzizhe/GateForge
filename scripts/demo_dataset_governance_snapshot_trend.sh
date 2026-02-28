#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_governance_snapshot_trend_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

run_dep_script() {
  local script_path="$1"
  local sentinel="$2"
  if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ] && [ -f "$sentinel" ]; then
    return 0
  fi
  bash "$script_path" >/dev/null
}

cat > "$OUT_DIR/previous_summary.json" <<'JSON'
{
  "status": "PASS",
  "risks": ["dataset_history_trend_needs_review"],
  "kpis": {
    "dataset_pipeline_deduplicated_cases": 8,
    "dataset_pipeline_failure_case_rate": 0.2,
    "dataset_governance_total_records": 4,
    "dataset_governance_trend_alert_count": 0,
    "dataset_failure_taxonomy_coverage_status": "PASS",
    "dataset_failure_taxonomy_total_cases": 4,
    "dataset_failure_taxonomy_unique_failure_types": 2,
    "dataset_failure_taxonomy_missing_failure_types_count": 3,
    "dataset_failure_taxonomy_missing_model_scales_count": 1,
    "dataset_failure_distribution_benchmark_status": "PASS",
    "dataset_failure_distribution_detection_rate_after": 0.8,
    "dataset_failure_distribution_false_positive_rate_after": 0.03,
    "dataset_failure_distribution_regression_rate_after": 0.1,
    "dataset_failure_distribution_drift_score": 0.2,
    "dataset_model_scale_ladder_status": "PASS",
    "dataset_model_scale_medium_cases": 2,
    "dataset_model_scale_large_cases": 1,
    "dataset_model_scale_main_ci_lane_count": 2,
    "dataset_failure_policy_patch_advisor_status": "PASS",
    "dataset_failure_policy_patch_confidence": 0.64,
    "dataset_failure_policy_patch_reason_count": 1,
    "dataset_modelica_library_provenance_guard_status": "PASS",
    "dataset_modelica_library_provenance_completeness_pct": 98.0,
    "dataset_modelica_library_unknown_license_ratio_pct": 0.0,
    "dataset_large_model_benchmark_pack_status": "PASS",
    "dataset_large_model_benchmark_pack_readiness_score": 80.0,
    "dataset_large_model_benchmark_selected_models": 2,
    "dataset_large_model_benchmark_selected_mutations": 6,
    "dataset_mutation_campaign_tracker_status": "PASS",
    "dataset_mutation_campaign_completion_ratio_pct": 82.0,
    "dataset_moat_public_scoreboard_status": "PASS",
    "dataset_moat_public_score": 78.0,
    "dataset_real_model_license_compliance_status": "PASS",
    "dataset_real_model_license_compliance_unknown_license_ratio_pct": 0.0,
    "dataset_real_model_license_compliance_disallowed_license_count": 0,
    "dataset_modelica_mutation_recipe_library_status": "PASS",
    "dataset_modelica_mutation_recipe_total": 8,
    "dataset_modelica_mutation_recipe_high_priority": 2,
    "dataset_real_model_failure_yield_status": "PASS",
    "dataset_real_model_failure_yield_per_accepted_model": 1.5,
    "dataset_real_model_failure_yield_execution_ratio_pct": 85.0,
    "dataset_real_model_intake_backlog_status": "PASS",
    "dataset_real_model_intake_backlog_item_count": 2,
    "dataset_real_model_intake_backlog_p0_count": 0,
    "dataset_modelica_moat_readiness_gate_status": "PASS",
    "dataset_modelica_moat_readiness_score": 79.0,
    "dataset_real_model_supply_health_status": "PASS",
    "dataset_real_model_supply_health_score": 82.0,
    "dataset_real_model_supply_gap_count": 0,
    "dataset_mutation_recipe_execution_audit_status": "PASS",
    "dataset_mutation_recipe_execution_coverage_pct": 78.0,
    "dataset_mutation_recipe_missing_count": 1,
    "dataset_modelica_release_candidate_gate_status": "PASS",
    "dataset_modelica_release_candidate_score": 80.0,
    "dataset_intake_growth_advisor_status": "PASS",
    "dataset_intake_growth_advisor_history_status": "PASS",
    "dataset_intake_growth_advisor_history_trend_status": "PASS",
    "dataset_intake_growth_execution_board_status": "PASS",
    "dataset_intake_growth_execution_board_execution_score": 82.0,
    "dataset_intake_growth_execution_board_history_status": "PASS",
    "dataset_intake_growth_execution_board_history_avg_execution_score": 81.0,
    "dataset_intake_growth_execution_board_history_critical_open_tasks_rate": 0.0,
    "dataset_intake_growth_execution_board_history_trend_status": "PASS",
    "dataset_real_model_intake_portfolio_status": "PASS",
    "dataset_real_model_intake_portfolio_total_real_models": 3,
    "dataset_real_model_intake_portfolio_large_models": 1,
    "dataset_real_model_intake_portfolio_license_clean_ratio_pct": 100.0,
    "dataset_mutation_coverage_depth_status": "PASS",
    "dataset_mutation_coverage_depth_score": 88.0,
    "dataset_mutation_coverage_depth_uncovered_cells_count": 0,
    "dataset_failure_distribution_stability_status": "PASS",
    "dataset_failure_distribution_stability_score": 82.0,
    "dataset_failure_distribution_stability_rare_failure_replay_rate": 1.0,
    "dataset_failure_distribution_stability_delta_drift": 0.01,
    "dataset_moat_anchor_brief_status": "PASS",
    "dataset_moat_anchor_brief_score": 79.0,
    "dataset_moat_anchor_brief_history_status": "PASS",
    "dataset_moat_anchor_brief_history_total_records": 3,
    "dataset_moat_anchor_brief_history_publish_rate": 0.67,
    "dataset_moat_anchor_brief_history_trend_status": "PASS",
    "dataset_promotion_effectiveness_history_trend_status": "PASS",
    "dataset_promotion_effectiveness_history_latest_decision": "KEEP"
  }
}
JSON

run_dep_script "scripts/demo_dataset_governance_snapshot.sh" "artifacts/dataset_governance_snapshot_demo/summary.json"

python3 -m gateforge.dataset_governance_snapshot_trend \
  --summary artifacts/dataset_governance_snapshot_demo/summary.json \
  --previous-summary "$OUT_DIR/previous_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_governance_snapshot_trend_demo")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
trend = payload.get("trend", {})
flags = {
    "has_status_transition": "PASS" if isinstance(trend.get("status_transition"), str) and "->" in trend.get("status_transition", "") else "FAIL",
    "has_kpi_delta": "PASS" if isinstance(trend.get("kpi_delta"), dict) else "FAIL",
    "has_status_delta": "PASS" if isinstance(trend.get("status_delta"), dict) else "FAIL",
    "has_severity_fields": "PASS" if isinstance(trend.get("severity_score"), int) and trend.get("severity_level") in {"low", "medium", "high"} else "FAIL",
    "has_new_risks_list": "PASS" if isinstance(trend.get("new_risks"), list) else "FAIL",
    "has_resolved_risks_list": "PASS" if isinstance(trend.get("resolved_risks"), list) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "status": payload.get("status"),
    "status_transition": trend.get("status_transition"),
    "severity_score": trend.get("severity_score"),
    "severity_level": trend.get("severity_level"),
    "new_risks_count": len(trend.get("new_risks", [])) if isinstance(trend.get("new_risks"), list) else 0,
    "resolved_risks_count": len(trend.get("resolved_risks", [])) if isinstance(trend.get("resolved_risks"), list) else 0,
    "promotion_effectiveness_history_trend_transition": (trend.get("status_delta") or {}).get(
        "dataset_promotion_effectiveness_history_trend_status_transition"
    ),
    "failure_taxonomy_coverage_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_failure_taxonomy_coverage_status_transition"
    ),
    "failure_distribution_benchmark_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_failure_distribution_benchmark_status_transition"
    ),
    "model_scale_ladder_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_model_scale_ladder_status_transition"
    ),
    "failure_policy_patch_advisor_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_failure_policy_patch_advisor_status_transition"
    ),
    "modelica_library_provenance_guard_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_modelica_library_provenance_guard_status_transition"
    ),
    "large_model_benchmark_pack_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_large_model_benchmark_pack_status_transition"
    ),
    "mutation_campaign_tracker_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_mutation_campaign_tracker_status_transition"
    ),
    "moat_public_scoreboard_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_moat_public_scoreboard_status_transition"
    ),
    "real_model_license_compliance_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_real_model_license_compliance_status_transition"
    ),
    "modelica_mutation_recipe_library_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_modelica_mutation_recipe_library_status_transition"
    ),
    "real_model_failure_yield_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_real_model_failure_yield_status_transition"
    ),
    "real_model_intake_backlog_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_real_model_intake_backlog_status_transition"
    ),
    "modelica_moat_readiness_gate_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_modelica_moat_readiness_gate_status_transition"
    ),
    "real_model_supply_health_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_real_model_supply_health_status_transition"
    ),
    "mutation_recipe_execution_audit_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_mutation_recipe_execution_audit_status_transition"
    ),
    "modelica_release_candidate_gate_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_modelica_release_candidate_gate_status_transition"
    ),
    "intake_growth_advisor_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_intake_growth_advisor_status_transition"
    ),
    "intake_growth_advisor_history_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_intake_growth_advisor_history_status_transition"
    ),
    "intake_growth_advisor_history_trend_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_intake_growth_advisor_history_trend_status_transition"
    ),
    "intake_growth_execution_board_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_intake_growth_execution_board_status_transition"
    ),
    "intake_growth_execution_board_history_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_intake_growth_execution_board_history_status_transition"
    ),
    "intake_growth_execution_board_history_trend_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_intake_growth_execution_board_history_trend_status_transition"
    ),
    "real_model_intake_portfolio_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_real_model_intake_portfolio_status_transition"
    ),
    "mutation_coverage_depth_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_mutation_coverage_depth_status_transition"
    ),
    "failure_distribution_stability_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_failure_distribution_stability_status_transition"
    ),
    "moat_anchor_brief_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_moat_anchor_brief_status_transition"
    ),
    "moat_anchor_brief_history_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_moat_anchor_brief_history_status_transition"
    ),
    "moat_anchor_brief_history_trend_status_transition": (trend.get("status_delta") or {}).get(
        "dataset_moat_anchor_brief_history_trend_status_transition"
    ),
    "status_delta_alert_count": len((trend.get("status_delta") or {}).get("alerts") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(out / "demo_summary.md").write_text(
    "\n".join(
        [
            "# Dataset Governance Snapshot Trend Demo",
            "",
            f"- status: `{demo['status']}`",
            f"- status_transition: `{demo['status_transition']}`",
            f"- severity_score: `{demo['severity_score']}`",
            f"- severity_level: `{demo['severity_level']}`",
            f"- new_risks_count: `{demo['new_risks_count']}`",
            f"- resolved_risks_count: `{demo['resolved_risks_count']}`",
            f"- promotion_effectiveness_history_trend_transition: `{demo['promotion_effectiveness_history_trend_transition']}`",
            f"- failure_taxonomy_coverage_status_transition: `{demo['failure_taxonomy_coverage_status_transition']}`",
            f"- failure_distribution_benchmark_status_transition: `{demo['failure_distribution_benchmark_status_transition']}`",
            f"- model_scale_ladder_status_transition: `{demo['model_scale_ladder_status_transition']}`",
            f"- failure_policy_patch_advisor_status_transition: `{demo['failure_policy_patch_advisor_status_transition']}`",
            f"- modelica_library_provenance_guard_status_transition: `{demo['modelica_library_provenance_guard_status_transition']}`",
            f"- large_model_benchmark_pack_status_transition: `{demo['large_model_benchmark_pack_status_transition']}`",
            f"- mutation_campaign_tracker_status_transition: `{demo['mutation_campaign_tracker_status_transition']}`",
            f"- moat_public_scoreboard_status_transition: `{demo['moat_public_scoreboard_status_transition']}`",
            f"- real_model_license_compliance_status_transition: `{demo['real_model_license_compliance_status_transition']}`",
            f"- modelica_mutation_recipe_library_status_transition: `{demo['modelica_mutation_recipe_library_status_transition']}`",
            f"- real_model_failure_yield_status_transition: `{demo['real_model_failure_yield_status_transition']}`",
            f"- real_model_intake_backlog_status_transition: `{demo['real_model_intake_backlog_status_transition']}`",
            f"- modelica_moat_readiness_gate_status_transition: `{demo['modelica_moat_readiness_gate_status_transition']}`",
            f"- real_model_supply_health_status_transition: `{demo['real_model_supply_health_status_transition']}`",
            f"- mutation_recipe_execution_audit_status_transition: `{demo['mutation_recipe_execution_audit_status_transition']}`",
            f"- modelica_release_candidate_gate_status_transition: `{demo['modelica_release_candidate_gate_status_transition']}`",
            f"- intake_growth_advisor_status_transition: `{demo['intake_growth_advisor_status_transition']}`",
            f"- intake_growth_advisor_history_status_transition: `{demo['intake_growth_advisor_history_status_transition']}`",
            f"- intake_growth_advisor_history_trend_status_transition: `{demo['intake_growth_advisor_history_trend_status_transition']}`",
            f"- intake_growth_execution_board_status_transition: `{demo['intake_growth_execution_board_status_transition']}`",
            f"- intake_growth_execution_board_history_status_transition: `{demo['intake_growth_execution_board_history_status_transition']}`",
            f"- intake_growth_execution_board_history_trend_status_transition: `{demo['intake_growth_execution_board_history_trend_status_transition']}`",
            f"- real_model_intake_portfolio_status_transition: `{demo['real_model_intake_portfolio_status_transition']}`",
            f"- mutation_coverage_depth_status_transition: `{demo['mutation_coverage_depth_status_transition']}`",
            f"- failure_distribution_stability_status_transition: `{demo['failure_distribution_stability_status_transition']}`",
            f"- moat_anchor_brief_status_transition: `{demo['moat_anchor_brief_status_transition']}`",
            f"- moat_anchor_brief_history_status_transition: `{demo['moat_anchor_brief_history_status_transition']}`",
            f"- moat_anchor_brief_history_trend_status_transition: `{demo['moat_anchor_brief_history_trend_status_transition']}`",
            f"- status_delta_alert_count: `{demo['status_delta_alert_count']}`",
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
