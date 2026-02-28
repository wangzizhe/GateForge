from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _status_from_signals(signals: dict) -> str:
    if signals.get("dataset_pipeline_bundle_fail"):
        return "FAIL"
    if signals.get("dataset_policy_effectiveness_rollback_review"):
        return "FAIL"
    if signals.get("dataset_governance_latest_fail"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_governance_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_strategy_suggests_tighten"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_strategy_apply_latest_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_strategy_apply_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_latest_block"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_apply_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_apply_latest_fail"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_rollback_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_promotion_effectiveness_history_latest_rollback_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_failure_taxonomy_coverage_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_failure_distribution_benchmark_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_model_scale_ladder_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_failure_policy_patch_advisor_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_modelica_library_provenance_guard_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_large_model_benchmark_pack_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_mutation_campaign_tracker_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_moat_public_scoreboard_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_real_model_license_compliance_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_modelica_mutation_recipe_library_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_real_model_failure_yield_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_real_model_intake_backlog_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_modelica_moat_readiness_gate_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_real_model_supply_health_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_mutation_recipe_execution_audit_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_modelica_release_candidate_gate_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_milestone_checkpoint_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_milestone_checkpoint_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_milestone_public_brief_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_intake_growth_advisor_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_intake_growth_advisor_history_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_intake_growth_advisor_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_intake_growth_execution_board_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_intake_growth_execution_board_history_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_intake_growth_execution_board_history_trend_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_real_model_intake_portfolio_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_mutation_coverage_depth_needs_review"):
        return "NEEDS_REVIEW"
    if signals.get("dataset_failure_distribution_stability_needs_review"):
        return "NEEDS_REVIEW"
    return "PASS"


def _compute_summary(
    dataset_pipeline: dict,
    dataset_history: dict,
    dataset_history_trend: dict,
    dataset_governance: dict,
    dataset_governance_trend: dict,
    effectiveness: dict,
    strategy_advisor: dict,
    strategy_apply_history: dict,
    strategy_apply_history_trend: dict,
    promotion_history: dict,
    promotion_history_trend: dict,
    promotion_apply_history: dict,
    promotion_apply_history_trend: dict,
    promotion_effectiveness: dict,
    promotion_effectiveness_history: dict,
    promotion_effectiveness_history_trend: dict,
    failure_taxonomy_coverage: dict,
    failure_distribution_benchmark: dict,
    model_scale_ladder: dict,
    failure_policy_patch_advisor: dict,
    modelica_library_provenance_guard: dict,
    large_model_benchmark_pack: dict,
    mutation_campaign_tracker: dict,
    moat_public_scoreboard: dict,
    real_model_license_compliance: dict,
    modelica_mutation_recipe_library: dict,
    real_model_failure_yield: dict,
    real_model_intake_backlog: dict,
    modelica_moat_readiness_gate: dict,
    real_model_supply_health: dict,
    mutation_recipe_execution_audit: dict,
    modelica_release_candidate_gate: dict,
    milestone_checkpoint: dict,
    milestone_checkpoint_trend: dict,
    milestone_public_brief: dict,
    intake_growth_advisor: dict,
    intake_growth_advisor_history: dict,
    intake_growth_advisor_history_trend: dict,
    intake_growth_execution_board: dict,
    intake_growth_execution_board_history: dict,
    intake_growth_execution_board_history_trend: dict,
    real_model_intake_portfolio: dict,
    mutation_coverage_depth: dict,
    failure_distribution_stability: dict,
) -> dict:
    strategy_advice = (
        strategy_advisor.get("advice")
        if isinstance(strategy_advisor.get("advice"), dict)
        else {}
    )
    trend_alerts = (
        (dataset_governance_trend.get("trend") or {}).get("alerts")
        if isinstance(dataset_governance_trend.get("trend"), dict)
        else []
    )
    if not isinstance(trend_alerts, list):
        trend_alerts = []

    signals = {
        "dataset_pipeline_bundle_fail": str(dataset_pipeline.get("bundle_status") or "") == "FAIL",
        "dataset_governance_latest_fail": str(dataset_governance.get("latest_status") or "") == "FAIL",
        "dataset_governance_trend_needs_review": str(dataset_governance_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_history_trend_needs_review": str(dataset_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_policy_effectiveness_rollback_review": str(effectiveness.get("decision") or "") == "ROLLBACK_REVIEW",
        "dataset_strategy_suggests_tighten": str(strategy_advice.get("suggested_policy_profile") or "") == "dataset_strict",
        "dataset_strategy_apply_latest_needs_review": str(strategy_apply_history.get("latest_final_status") or "") == "NEEDS_REVIEW",
        "dataset_strategy_apply_latest_fail": str(strategy_apply_history.get("latest_final_status") or "") == "FAIL",
        "dataset_strategy_apply_trend_needs_review": str(strategy_apply_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_promotion_latest_block": str(promotion_history.get("latest_decision") or "") == "BLOCK",
        "dataset_promotion_trend_needs_review": str(promotion_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_promotion_apply_latest_fail": str(promotion_apply_history.get("latest_final_status") or "") == "FAIL",
        "dataset_promotion_apply_trend_needs_review": str(promotion_apply_history_trend.get("status") or "") == "NEEDS_REVIEW",
        "dataset_promotion_effectiveness_rollback_review": str(promotion_effectiveness.get("decision") or "") == "ROLLBACK_REVIEW",
        "dataset_promotion_effectiveness_needs_review": str(promotion_effectiveness.get("decision") or "") == "NEEDS_REVIEW",
        "dataset_promotion_effectiveness_history_trend_needs_review": str(
            promotion_effectiveness_history_trend.get("status") or ""
        )
        == "NEEDS_REVIEW",
        "dataset_promotion_effectiveness_history_latest_rollback_review": str(
            promotion_effectiveness_history.get("latest_decision") or ""
        )
        == "ROLLBACK_REVIEW",
        "dataset_failure_taxonomy_coverage_needs_review": str(failure_taxonomy_coverage.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_failure_distribution_benchmark_needs_review": str(failure_distribution_benchmark.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_model_scale_ladder_needs_review": str(model_scale_ladder.get("status") or "") in {"NEEDS_REVIEW", "FAIL"},
        "dataset_failure_policy_patch_advisor_needs_review": str(failure_policy_patch_advisor.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_modelica_library_provenance_guard_needs_review": str(
            modelica_library_provenance_guard.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_large_model_benchmark_pack_needs_review": str(large_model_benchmark_pack.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_mutation_campaign_tracker_needs_review": str(mutation_campaign_tracker.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_moat_public_scoreboard_needs_review": str(moat_public_scoreboard.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_real_model_license_compliance_needs_review": str(real_model_license_compliance.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_modelica_mutation_recipe_library_needs_review": str(
            modelica_mutation_recipe_library.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_real_model_failure_yield_needs_review": str(real_model_failure_yield.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_real_model_intake_backlog_needs_review": str(real_model_intake_backlog.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_modelica_moat_readiness_gate_needs_review": str(modelica_moat_readiness_gate.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_real_model_supply_health_needs_review": str(real_model_supply_health.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_mutation_recipe_execution_audit_needs_review": str(mutation_recipe_execution_audit.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_modelica_release_candidate_gate_needs_review": str(modelica_release_candidate_gate.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_milestone_checkpoint_needs_review": str(milestone_checkpoint.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_milestone_checkpoint_trend_needs_review": str(milestone_checkpoint_trend.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_milestone_public_brief_needs_review": str(milestone_public_brief.get("milestone_status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_intake_growth_advisor_needs_review": str(intake_growth_advisor.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_intake_growth_advisor_history_needs_review": str(intake_growth_advisor_history.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_intake_growth_advisor_history_trend_needs_review": str(
            intake_growth_advisor_history_trend.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_intake_growth_execution_board_needs_review": str(
            intake_growth_execution_board.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_intake_growth_execution_board_history_needs_review": str(
            intake_growth_execution_board_history.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_intake_growth_execution_board_history_trend_needs_review": str(
            intake_growth_execution_board_history_trend.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_real_model_intake_portfolio_needs_review": str(real_model_intake_portfolio.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_mutation_coverage_depth_needs_review": str(mutation_coverage_depth.get("status") or "")
        in {"NEEDS_REVIEW", "FAIL"},
        "dataset_failure_distribution_stability_needs_review": str(
            failure_distribution_stability.get("status") or ""
        )
        in {"NEEDS_REVIEW", "FAIL"},
    }
    status = _status_from_signals(signals)

    risks: list[str] = []
    if signals["dataset_pipeline_bundle_fail"]:
        risks.append("dataset_pipeline_bundle_fail")
    if signals["dataset_governance_latest_fail"]:
        risks.append("dataset_governance_latest_fail")
    if signals["dataset_governance_trend_needs_review"]:
        risks.append("dataset_governance_trend_needs_review")
    if signals["dataset_history_trend_needs_review"]:
        risks.append("dataset_history_trend_needs_review")
    if signals["dataset_policy_effectiveness_rollback_review"]:
        risks.append("dataset_policy_effectiveness_rollback_review")
    if signals["dataset_strategy_suggests_tighten"]:
        risks.append("dataset_strategy_suggests_tighten")
    if signals["dataset_strategy_apply_latest_needs_review"]:
        risks.append("dataset_strategy_apply_latest_needs_review")
    if signals["dataset_strategy_apply_latest_fail"]:
        risks.append("dataset_strategy_apply_latest_fail")
    if signals["dataset_strategy_apply_trend_needs_review"]:
        risks.append("dataset_strategy_apply_trend_needs_review")
    if signals["dataset_promotion_latest_block"]:
        risks.append("dataset_promotion_latest_block")
    if signals["dataset_promotion_trend_needs_review"]:
        risks.append("dataset_promotion_trend_needs_review")
    if signals["dataset_promotion_apply_latest_fail"]:
        risks.append("dataset_promotion_apply_latest_fail")
    if signals["dataset_promotion_apply_trend_needs_review"]:
        risks.append("dataset_promotion_apply_trend_needs_review")
    if signals["dataset_promotion_effectiveness_rollback_review"]:
        risks.append("dataset_promotion_effectiveness_rollback_review")
    if signals["dataset_promotion_effectiveness_needs_review"]:
        risks.append("dataset_promotion_effectiveness_needs_review")
    if signals["dataset_promotion_effectiveness_history_trend_needs_review"]:
        risks.append("dataset_promotion_effectiveness_history_trend_needs_review")
    if signals["dataset_promotion_effectiveness_history_latest_rollback_review"]:
        risks.append("dataset_promotion_effectiveness_history_latest_rollback_review")
    if signals["dataset_failure_taxonomy_coverage_needs_review"]:
        risks.append("dataset_failure_taxonomy_coverage_needs_review")
    if signals["dataset_failure_distribution_benchmark_needs_review"]:
        risks.append("dataset_failure_distribution_benchmark_needs_review")
    if signals["dataset_model_scale_ladder_needs_review"]:
        risks.append("dataset_model_scale_ladder_needs_review")
    if signals["dataset_failure_policy_patch_advisor_needs_review"]:
        risks.append("dataset_failure_policy_patch_advisor_needs_review")
    if signals["dataset_modelica_library_provenance_guard_needs_review"]:
        risks.append("dataset_modelica_library_provenance_guard_needs_review")
    if signals["dataset_large_model_benchmark_pack_needs_review"]:
        risks.append("dataset_large_model_benchmark_pack_needs_review")
    if signals["dataset_mutation_campaign_tracker_needs_review"]:
        risks.append("dataset_mutation_campaign_tracker_needs_review")
    if signals["dataset_moat_public_scoreboard_needs_review"]:
        risks.append("dataset_moat_public_scoreboard_needs_review")
    if signals["dataset_real_model_license_compliance_needs_review"]:
        risks.append("dataset_real_model_license_compliance_needs_review")
    if signals["dataset_modelica_mutation_recipe_library_needs_review"]:
        risks.append("dataset_modelica_mutation_recipe_library_needs_review")
    if signals["dataset_real_model_failure_yield_needs_review"]:
        risks.append("dataset_real_model_failure_yield_needs_review")
    if signals["dataset_real_model_intake_backlog_needs_review"]:
        risks.append("dataset_real_model_intake_backlog_needs_review")
    if signals["dataset_modelica_moat_readiness_gate_needs_review"]:
        risks.append("dataset_modelica_moat_readiness_gate_needs_review")
    if signals["dataset_real_model_supply_health_needs_review"]:
        risks.append("dataset_real_model_supply_health_needs_review")
    if signals["dataset_mutation_recipe_execution_audit_needs_review"]:
        risks.append("dataset_mutation_recipe_execution_audit_needs_review")
    if signals["dataset_modelica_release_candidate_gate_needs_review"]:
        risks.append("dataset_modelica_release_candidate_gate_needs_review")
    if signals["dataset_milestone_checkpoint_needs_review"]:
        risks.append("dataset_milestone_checkpoint_needs_review")
    if signals["dataset_milestone_checkpoint_trend_needs_review"]:
        risks.append("dataset_milestone_checkpoint_trend_needs_review")
    if signals["dataset_milestone_public_brief_needs_review"]:
        risks.append("dataset_milestone_public_brief_needs_review")
    if signals["dataset_intake_growth_advisor_needs_review"]:
        risks.append("dataset_intake_growth_advisor_needs_review")
    if signals["dataset_intake_growth_advisor_history_needs_review"]:
        risks.append("dataset_intake_growth_advisor_history_needs_review")
    if signals["dataset_intake_growth_advisor_history_trend_needs_review"]:
        risks.append("dataset_intake_growth_advisor_history_trend_needs_review")
    if signals["dataset_intake_growth_execution_board_needs_review"]:
        risks.append("dataset_intake_growth_execution_board_needs_review")
    if signals["dataset_intake_growth_execution_board_history_needs_review"]:
        risks.append("dataset_intake_growth_execution_board_history_needs_review")
    if signals["dataset_intake_growth_execution_board_history_trend_needs_review"]:
        risks.append("dataset_intake_growth_execution_board_history_trend_needs_review")
    if signals["dataset_real_model_intake_portfolio_needs_review"]:
        risks.append("dataset_real_model_intake_portfolio_needs_review")
    if signals["dataset_mutation_coverage_depth_needs_review"]:
        risks.append("dataset_mutation_coverage_depth_needs_review")
    if signals["dataset_failure_distribution_stability_needs_review"]:
        risks.append("dataset_failure_distribution_stability_needs_review")

    policy_patch_advice = (
        failure_policy_patch_advisor.get("advice")
        if isinstance(failure_policy_patch_advisor.get("advice"), dict)
        else {}
    )
    policy_patch_reasons = policy_patch_advice.get("reasons") if isinstance(policy_patch_advice.get("reasons"), list) else []

    missing_failure_types = failure_taxonomy_coverage.get("missing_failure_types", [])
    if not isinstance(missing_failure_types, list):
        missing_failure_types = []
    missing_model_scales = failure_taxonomy_coverage.get("missing_model_scales", [])
    if not isinstance(missing_model_scales, list):
        missing_model_scales = []
    missing_stages = failure_taxonomy_coverage.get("missing_stages", [])
    if not isinstance(missing_stages, list):
        missing_stages = []

    kpis = {
        "dataset_pipeline_deduplicated_cases": _to_int(
            dataset_pipeline.get(
                "build_deduplicated_cases",
                dataset_pipeline.get("deduplicated_cases", dataset_pipeline.get("total_cases", 0)),
            )
        ),
        "dataset_pipeline_failure_case_rate": _to_float(
            dataset_pipeline.get("quality_failure_case_rate", dataset_pipeline.get("failure_case_rate", 0.0))
        ),
        "dataset_history_total_records": _to_int(dataset_history.get("total_records", 0)),
        "dataset_history_latest_failure_case_rate": _to_float(dataset_history.get("latest_failure_case_rate", 0.0)),
        "dataset_governance_total_records": _to_int(dataset_governance.get("total_records", 0)),
        "dataset_governance_latest_status": dataset_governance.get("latest_status"),
        "dataset_governance_trend_alert_count": len(trend_alerts),
        "dataset_policy_effectiveness_decision": effectiveness.get("decision"),
        "dataset_strategy_profile": strategy_advice.get("suggested_policy_profile"),
        "dataset_strategy_action": strategy_advice.get("suggested_action"),
        "dataset_strategy_apply_latest_final_status": strategy_apply_history.get("latest_final_status"),
        "dataset_strategy_apply_fail_rate": _to_float(strategy_apply_history.get("fail_rate", 0.0)),
        "dataset_strategy_apply_needs_review_rate": _to_float(strategy_apply_history.get("needs_review_rate", 0.0)),
        "dataset_strategy_apply_trend_status": strategy_apply_history_trend.get("status"),
        "dataset_promotion_latest_decision": promotion_history.get("latest_decision"),
        "dataset_promotion_hold_rate": _to_float(promotion_history.get("hold_rate", 0.0)),
        "dataset_promotion_block_rate": _to_float(promotion_history.get("block_rate", 0.0)),
        "dataset_promotion_trend_status": promotion_history_trend.get("status"),
        "dataset_promotion_apply_latest_final_status": promotion_apply_history.get("latest_final_status"),
        "dataset_promotion_apply_fail_rate": _to_float(promotion_apply_history.get("fail_rate", 0.0)),
        "dataset_promotion_apply_needs_review_rate": _to_float(promotion_apply_history.get("needs_review_rate", 0.0)),
        "dataset_promotion_apply_trend_status": promotion_apply_history_trend.get("status"),
        "dataset_promotion_effectiveness_decision": promotion_effectiveness.get("decision"),
        "dataset_promotion_effectiveness_history_latest_decision": promotion_effectiveness_history.get("latest_decision"),
        "dataset_promotion_effectiveness_history_trend_status": promotion_effectiveness_history_trend.get("status"),
        "dataset_failure_taxonomy_coverage_status": failure_taxonomy_coverage.get("status"),
        "dataset_failure_taxonomy_total_cases": _to_int(failure_taxonomy_coverage.get("total_cases", 0)),
        "dataset_failure_taxonomy_unique_failure_types": _to_int(
            failure_taxonomy_coverage.get("unique_failure_type_count", 0)
        ),
        "dataset_failure_taxonomy_missing_failure_types_count": len(missing_failure_types),
        "dataset_failure_taxonomy_missing_model_scales_count": len(missing_model_scales),
        "dataset_failure_taxonomy_missing_stages_count": len(missing_stages),
        "dataset_failure_distribution_benchmark_status": failure_distribution_benchmark.get("status"),
        "dataset_failure_distribution_detection_rate_after": _to_float(
            failure_distribution_benchmark.get("detection_rate_after", 0.0)
        ),
        "dataset_failure_distribution_false_positive_rate_after": _to_float(
            failure_distribution_benchmark.get("false_positive_rate_after", 0.0)
        ),
        "dataset_failure_distribution_regression_rate_after": _to_float(
            failure_distribution_benchmark.get("regression_rate_after", 0.0)
        ),
        "dataset_failure_distribution_drift_score": _to_float(
            failure_distribution_benchmark.get("distribution_drift_score", 0.0)
        ),
        "dataset_model_scale_ladder_status": model_scale_ladder.get("status"),
        "dataset_model_scale_medium_cases": _to_int(((model_scale_ladder.get("scale_counts") or {}).get("medium"))),
        "dataset_model_scale_large_cases": _to_int(((model_scale_ladder.get("scale_counts") or {}).get("large"))),
        "dataset_model_scale_medium_ready": bool(model_scale_ladder.get("medium_ready")),
        "dataset_model_scale_large_ready": bool(model_scale_ladder.get("large_ready")),
        "dataset_model_scale_main_ci_lane_count": len(((model_scale_ladder.get("ci_recommendation") or {}).get("main") or [])),
        "dataset_model_scale_optional_ci_lane_count": len(
            ((model_scale_ladder.get("ci_recommendation") or {}).get("optional") or [])
        ),
        "dataset_failure_policy_patch_advisor_status": failure_policy_patch_advisor.get("status"),
        "dataset_failure_policy_patch_suggested_action": policy_patch_advice.get("suggested_action"),
        "dataset_failure_policy_patch_confidence": _to_float(policy_patch_advice.get("confidence", 0.0)),
        "dataset_failure_policy_patch_reason_count": len(policy_patch_reasons),
        "dataset_modelica_library_provenance_guard_status": modelica_library_provenance_guard.get("status"),
        "dataset_modelica_library_provenance_completeness_pct": _to_float(
            modelica_library_provenance_guard.get("provenance_completeness_pct", 0.0)
        ),
        "dataset_modelica_library_unknown_license_ratio_pct": _to_float(
            modelica_library_provenance_guard.get("unknown_license_ratio_pct", 0.0)
        ),
        "dataset_large_model_benchmark_pack_status": large_model_benchmark_pack.get("status"),
        "dataset_large_model_benchmark_pack_readiness_score": _to_float(
            large_model_benchmark_pack.get("pack_readiness_score", 0.0)
        ),
        "dataset_large_model_benchmark_selected_models": _to_int(
            large_model_benchmark_pack.get("selected_large_models", 0)
        ),
        "dataset_large_model_benchmark_selected_mutations": _to_int(
            large_model_benchmark_pack.get("selected_large_mutations", 0)
        ),
        "dataset_mutation_campaign_tracker_status": mutation_campaign_tracker.get("status"),
        "dataset_mutation_campaign_completion_ratio_pct": _to_float(
            mutation_campaign_tracker.get("completion_ratio_pct", 0.0)
        ),
        "dataset_mutation_campaign_phase": mutation_campaign_tracker.get("campaign_phase"),
        "dataset_moat_public_scoreboard_status": moat_public_scoreboard.get("status"),
        "dataset_moat_public_score": _to_float(moat_public_scoreboard.get("moat_public_score", 0.0)),
        "dataset_moat_public_verdict": moat_public_scoreboard.get("verdict"),
        "dataset_real_model_license_compliance_status": real_model_license_compliance.get("status"),
        "dataset_real_model_license_compliance_unknown_license_ratio_pct": _to_float(
            real_model_license_compliance.get("unknown_license_ratio_pct", 0.0)
        ),
        "dataset_real_model_license_compliance_disallowed_license_count": _to_int(
            real_model_license_compliance.get("disallowed_license_count", 0)
        ),
        "dataset_modelica_mutation_recipe_library_status": modelica_mutation_recipe_library.get("status"),
        "dataset_modelica_mutation_recipe_total": _to_int(modelica_mutation_recipe_library.get("total_recipes", 0)),
        "dataset_modelica_mutation_recipe_high_priority": _to_int(
            modelica_mutation_recipe_library.get("high_priority_recipes", 0)
        ),
        "dataset_modelica_mutation_recipe_coverage_score": _to_float(
            modelica_mutation_recipe_library.get("recipe_coverage_score", 0.0)
        ),
        "dataset_real_model_failure_yield_status": real_model_failure_yield.get("status"),
        "dataset_real_model_failure_yield_per_accepted_model": _to_float(
            real_model_failure_yield.get("yield_per_accepted_model", 0.0)
        ),
        "dataset_real_model_failure_yield_execution_ratio_pct": _to_float(
            real_model_failure_yield.get("matrix_execution_ratio_pct", 0.0)
        ),
        "dataset_real_model_failure_effective_yield_score": _to_float(
            real_model_failure_yield.get("effective_yield_score", 0.0)
        ),
        "dataset_real_model_failure_yield_band": real_model_failure_yield.get("yield_band"),
        "dataset_real_model_intake_backlog_status": real_model_intake_backlog.get("status"),
        "dataset_real_model_intake_backlog_item_count": _to_int(real_model_intake_backlog.get("backlog_item_count", 0)),
        "dataset_real_model_intake_backlog_p0_count": _to_int(real_model_intake_backlog.get("p0_count", 0)),
        "dataset_modelica_moat_readiness_gate_status": modelica_moat_readiness_gate.get("status"),
        "dataset_modelica_moat_readiness_score": _to_float(modelica_moat_readiness_gate.get("moat_readiness_score", 0.0)),
        "dataset_modelica_moat_release_recommendation": modelica_moat_readiness_gate.get("release_recommendation"),
        "dataset_modelica_moat_confidence_level": modelica_moat_readiness_gate.get("confidence_level"),
        "dataset_modelica_moat_critical_blocker_count": len(modelica_moat_readiness_gate.get("critical_blockers") or []),
        "dataset_real_model_license_risk_score": _to_float(real_model_license_compliance.get("license_risk_score", 0.0)),
        "dataset_real_model_supply_health_status": real_model_supply_health.get("status"),
        "dataset_real_model_supply_health_score": _to_float(real_model_supply_health.get("supply_health_score", 0.0)),
        "dataset_real_model_supply_gap_count": _to_int(real_model_supply_health.get("supply_gap_count", 0)),
        "dataset_mutation_recipe_execution_audit_status": mutation_recipe_execution_audit.get("status"),
        "dataset_mutation_recipe_execution_coverage_pct": _to_float(
            mutation_recipe_execution_audit.get("execution_coverage_pct", 0.0)
        ),
        "dataset_mutation_recipe_missing_count": _to_int(mutation_recipe_execution_audit.get("missing_recipe_count", 0)),
        "dataset_modelica_release_candidate_gate_status": modelica_release_candidate_gate.get("status"),
        "dataset_modelica_release_candidate_score": _to_float(
            modelica_release_candidate_gate.get("release_candidate_score", 0.0)
        ),
        "dataset_modelica_release_candidate_decision": modelica_release_candidate_gate.get("candidate_decision"),
        "dataset_milestone_checkpoint_status": milestone_checkpoint.get("status"),
        "dataset_milestone_checkpoint_score": _to_float(milestone_checkpoint.get("checkpoint_score", 0.0)),
        "dataset_milestone_checkpoint_decision": milestone_checkpoint.get("milestone_decision"),
        "dataset_milestone_checkpoint_trend_status": milestone_checkpoint_trend.get("status"),
        "dataset_milestone_checkpoint_trend_transition": ((milestone_checkpoint_trend.get("trend") or {}).get("status_transition"))
        if isinstance(milestone_checkpoint_trend.get("trend"), dict)
        else None,
        "dataset_milestone_public_brief_status": milestone_public_brief.get("milestone_status"),
        "dataset_milestone_public_brief_decision": milestone_public_brief.get("milestone_decision"),
        "dataset_intake_growth_advisor_status": intake_growth_advisor.get("status"),
        "dataset_intake_growth_suggested_action": (
            (intake_growth_advisor.get("advice") or {}).get("suggested_action")
            if isinstance(intake_growth_advisor.get("advice"), dict)
            else None
        ),
        "dataset_intake_growth_backlog_action_count": len(
            ((intake_growth_advisor.get("advice") or {}).get("backlog_actions") or [])
            if isinstance(intake_growth_advisor.get("advice"), dict)
            else []
        ),
        "dataset_intake_growth_advisor_history_status": intake_growth_advisor_history.get("status"),
        "dataset_intake_growth_advisor_history_latest_action": intake_growth_advisor_history.get(
            "latest_suggested_action"
        ),
        "dataset_intake_growth_advisor_history_recovery_plan_rate": _to_float(
            intake_growth_advisor_history.get("recovery_plan_rate", 0.0)
        ),
        "dataset_intake_growth_advisor_history_trend_status": intake_growth_advisor_history_trend.get("status"),
        "dataset_intake_growth_advisor_history_trend_alert_count": len(
            ((intake_growth_advisor_history_trend.get("trend") or {}).get("alerts") or [])
            if isinstance(intake_growth_advisor_history_trend.get("trend"), dict)
            else []
        ),
        "dataset_intake_growth_execution_board_status": intake_growth_execution_board.get("status"),
        "dataset_intake_growth_execution_board_execution_score": _to_float(
            intake_growth_execution_board.get("execution_score", 0.0)
        ),
        "dataset_intake_growth_execution_board_critical_open_tasks": _to_int(
            intake_growth_execution_board.get("critical_open_tasks", 0)
        ),
        "dataset_intake_growth_execution_board_projected_weeks_to_target": _to_int(
            intake_growth_execution_board.get("projected_weeks_to_target", 0)
        ),
        "dataset_intake_growth_execution_board_history_status": intake_growth_execution_board_history.get("status"),
        "dataset_intake_growth_execution_board_history_avg_execution_score": _to_float(
            intake_growth_execution_board_history.get("avg_execution_score", 0.0)
        ),
        "dataset_intake_growth_execution_board_history_critical_open_tasks_rate": _to_float(
            intake_growth_execution_board_history.get("critical_open_tasks_rate", 0.0)
        ),
        "dataset_intake_growth_execution_board_history_trend_status": intake_growth_execution_board_history_trend.get(
            "status"
        ),
        "dataset_intake_growth_execution_board_history_trend_alert_count": len(
            ((intake_growth_execution_board_history_trend.get("trend") or {}).get("alerts") or [])
            if isinstance(intake_growth_execution_board_history_trend.get("trend"), dict)
            else []
        ),
        "dataset_real_model_intake_portfolio_status": real_model_intake_portfolio.get("status"),
        "dataset_real_model_intake_portfolio_total_real_models": _to_int(
            real_model_intake_portfolio.get("total_real_models", 0)
        ),
        "dataset_real_model_intake_portfolio_large_models": _to_int(
            real_model_intake_portfolio.get("large_models", 0)
        ),
        "dataset_real_model_intake_portfolio_license_clean_ratio_pct": _to_float(
            real_model_intake_portfolio.get("license_clean_ratio_pct", 0.0)
        ),
        "dataset_real_model_intake_portfolio_active_domains_count": _to_int(
            real_model_intake_portfolio.get("active_domains_count", 0)
        ),
        "dataset_mutation_coverage_depth_status": mutation_coverage_depth.get("status"),
        "dataset_mutation_coverage_depth_score": _to_float(
            mutation_coverage_depth.get("coverage_depth_score", 0.0)
        ),
        "dataset_mutation_coverage_depth_uncovered_cells_count": _to_int(
            mutation_coverage_depth.get("uncovered_cells_count", 0)
        ),
        "dataset_mutation_coverage_depth_high_risk_gaps_count": _to_int(
            mutation_coverage_depth.get("high_risk_gaps_count", 0)
        ),
        "dataset_failure_distribution_stability_status": failure_distribution_stability.get("status"),
        "dataset_failure_distribution_stability_score": _to_float(
            failure_distribution_stability.get("stability_score", 0.0)
        ),
        "dataset_failure_distribution_stability_drift_band": failure_distribution_stability.get("drift_band"),
        "dataset_failure_distribution_stability_rare_failure_replay_rate": _to_float(
            failure_distribution_stability.get("rare_failure_replay_rate", 0.0)
        ),
        "dataset_failure_distribution_stability_delta_drift": _to_float(
            failure_distribution_stability.get("delta_distribution_drift_score", 0.0)
        ),
    }
    return {
        "status": status,
        "signals": signals,
        "risks": risks,
        "kpis": kpis,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    kpis = summary.get("kpis", {})
    lines = [
        "# GateForge Dataset Governance Snapshot",
        "",
        f"- status: `{summary.get('status')}`",
        f"- dataset_pipeline_deduplicated_cases: `{kpis.get('dataset_pipeline_deduplicated_cases')}`",
        f"- dataset_pipeline_failure_case_rate: `{kpis.get('dataset_pipeline_failure_case_rate')}`",
        f"- dataset_history_total_records: `{kpis.get('dataset_history_total_records')}`",
        f"- dataset_governance_total_records: `{kpis.get('dataset_governance_total_records')}`",
        f"- dataset_policy_effectiveness_decision: `{kpis.get('dataset_policy_effectiveness_decision')}`",
        f"- dataset_strategy_profile: `{kpis.get('dataset_strategy_profile')}`",
        f"- dataset_strategy_action: `{kpis.get('dataset_strategy_action')}`",
        f"- dataset_strategy_apply_latest_final_status: `{kpis.get('dataset_strategy_apply_latest_final_status')}`",
        f"- dataset_strategy_apply_fail_rate: `{kpis.get('dataset_strategy_apply_fail_rate')}`",
        f"- dataset_strategy_apply_needs_review_rate: `{kpis.get('dataset_strategy_apply_needs_review_rate')}`",
        f"- dataset_strategy_apply_trend_status: `{kpis.get('dataset_strategy_apply_trend_status')}`",
        f"- dataset_promotion_latest_decision: `{kpis.get('dataset_promotion_latest_decision')}`",
        f"- dataset_promotion_hold_rate: `{kpis.get('dataset_promotion_hold_rate')}`",
        f"- dataset_promotion_block_rate: `{kpis.get('dataset_promotion_block_rate')}`",
        f"- dataset_promotion_trend_status: `{kpis.get('dataset_promotion_trend_status')}`",
        f"- dataset_promotion_apply_latest_final_status: `{kpis.get('dataset_promotion_apply_latest_final_status')}`",
        f"- dataset_promotion_apply_fail_rate: `{kpis.get('dataset_promotion_apply_fail_rate')}`",
        f"- dataset_promotion_apply_needs_review_rate: `{kpis.get('dataset_promotion_apply_needs_review_rate')}`",
        f"- dataset_promotion_apply_trend_status: `{kpis.get('dataset_promotion_apply_trend_status')}`",
        f"- dataset_promotion_effectiveness_decision: `{kpis.get('dataset_promotion_effectiveness_decision')}`",
        f"- dataset_promotion_effectiveness_history_latest_decision: `{kpis.get('dataset_promotion_effectiveness_history_latest_decision')}`",
        f"- dataset_promotion_effectiveness_history_trend_status: `{kpis.get('dataset_promotion_effectiveness_history_trend_status')}`",
        f"- dataset_failure_taxonomy_coverage_status: `{kpis.get('dataset_failure_taxonomy_coverage_status')}`",
        f"- dataset_failure_taxonomy_total_cases: `{kpis.get('dataset_failure_taxonomy_total_cases')}`",
        f"- dataset_failure_taxonomy_unique_failure_types: `{kpis.get('dataset_failure_taxonomy_unique_failure_types')}`",
        f"- dataset_failure_taxonomy_missing_failure_types_count: `{kpis.get('dataset_failure_taxonomy_missing_failure_types_count')}`",
        f"- dataset_failure_taxonomy_missing_model_scales_count: `{kpis.get('dataset_failure_taxonomy_missing_model_scales_count')}`",
        f"- dataset_failure_taxonomy_missing_stages_count: `{kpis.get('dataset_failure_taxonomy_missing_stages_count')}`",
        f"- dataset_failure_distribution_benchmark_status: `{kpis.get('dataset_failure_distribution_benchmark_status')}`",
        f"- dataset_failure_distribution_detection_rate_after: `{kpis.get('dataset_failure_distribution_detection_rate_after')}`",
        f"- dataset_failure_distribution_false_positive_rate_after: `{kpis.get('dataset_failure_distribution_false_positive_rate_after')}`",
        f"- dataset_failure_distribution_regression_rate_after: `{kpis.get('dataset_failure_distribution_regression_rate_after')}`",
        f"- dataset_failure_distribution_drift_score: `{kpis.get('dataset_failure_distribution_drift_score')}`",
        f"- dataset_model_scale_ladder_status: `{kpis.get('dataset_model_scale_ladder_status')}`",
        f"- dataset_model_scale_medium_cases: `{kpis.get('dataset_model_scale_medium_cases')}`",
        f"- dataset_model_scale_large_cases: `{kpis.get('dataset_model_scale_large_cases')}`",
        f"- dataset_model_scale_medium_ready: `{kpis.get('dataset_model_scale_medium_ready')}`",
        f"- dataset_model_scale_large_ready: `{kpis.get('dataset_model_scale_large_ready')}`",
        f"- dataset_model_scale_main_ci_lane_count: `{kpis.get('dataset_model_scale_main_ci_lane_count')}`",
        f"- dataset_model_scale_optional_ci_lane_count: `{kpis.get('dataset_model_scale_optional_ci_lane_count')}`",
        f"- dataset_failure_policy_patch_advisor_status: `{kpis.get('dataset_failure_policy_patch_advisor_status')}`",
        f"- dataset_failure_policy_patch_suggested_action: `{kpis.get('dataset_failure_policy_patch_suggested_action')}`",
        f"- dataset_failure_policy_patch_confidence: `{kpis.get('dataset_failure_policy_patch_confidence')}`",
        f"- dataset_failure_policy_patch_reason_count: `{kpis.get('dataset_failure_policy_patch_reason_count')}`",
        f"- dataset_modelica_library_provenance_guard_status: `{kpis.get('dataset_modelica_library_provenance_guard_status')}`",
        f"- dataset_modelica_library_provenance_completeness_pct: `{kpis.get('dataset_modelica_library_provenance_completeness_pct')}`",
        f"- dataset_modelica_library_unknown_license_ratio_pct: `{kpis.get('dataset_modelica_library_unknown_license_ratio_pct')}`",
        f"- dataset_large_model_benchmark_pack_status: `{kpis.get('dataset_large_model_benchmark_pack_status')}`",
        f"- dataset_large_model_benchmark_pack_readiness_score: `{kpis.get('dataset_large_model_benchmark_pack_readiness_score')}`",
        f"- dataset_large_model_benchmark_selected_models: `{kpis.get('dataset_large_model_benchmark_selected_models')}`",
        f"- dataset_large_model_benchmark_selected_mutations: `{kpis.get('dataset_large_model_benchmark_selected_mutations')}`",
        f"- dataset_mutation_campaign_tracker_status: `{kpis.get('dataset_mutation_campaign_tracker_status')}`",
        f"- dataset_mutation_campaign_completion_ratio_pct: `{kpis.get('dataset_mutation_campaign_completion_ratio_pct')}`",
        f"- dataset_mutation_campaign_phase: `{kpis.get('dataset_mutation_campaign_phase')}`",
        f"- dataset_moat_public_scoreboard_status: `{kpis.get('dataset_moat_public_scoreboard_status')}`",
        f"- dataset_moat_public_score: `{kpis.get('dataset_moat_public_score')}`",
        f"- dataset_moat_public_verdict: `{kpis.get('dataset_moat_public_verdict')}`",
        f"- dataset_real_model_license_compliance_status: `{kpis.get('dataset_real_model_license_compliance_status')}`",
        f"- dataset_real_model_license_compliance_unknown_license_ratio_pct: `{kpis.get('dataset_real_model_license_compliance_unknown_license_ratio_pct')}`",
        f"- dataset_real_model_license_compliance_disallowed_license_count: `{kpis.get('dataset_real_model_license_compliance_disallowed_license_count')}`",
        f"- dataset_modelica_mutation_recipe_library_status: `{kpis.get('dataset_modelica_mutation_recipe_library_status')}`",
        f"- dataset_modelica_mutation_recipe_total: `{kpis.get('dataset_modelica_mutation_recipe_total')}`",
        f"- dataset_modelica_mutation_recipe_high_priority: `{kpis.get('dataset_modelica_mutation_recipe_high_priority')}`",
        f"- dataset_modelica_mutation_recipe_coverage_score: `{kpis.get('dataset_modelica_mutation_recipe_coverage_score')}`",
        f"- dataset_real_model_failure_yield_status: `{kpis.get('dataset_real_model_failure_yield_status')}`",
        f"- dataset_real_model_failure_yield_per_accepted_model: `{kpis.get('dataset_real_model_failure_yield_per_accepted_model')}`",
        f"- dataset_real_model_failure_yield_execution_ratio_pct: `{kpis.get('dataset_real_model_failure_yield_execution_ratio_pct')}`",
        f"- dataset_real_model_failure_effective_yield_score: `{kpis.get('dataset_real_model_failure_effective_yield_score')}`",
        f"- dataset_real_model_failure_yield_band: `{kpis.get('dataset_real_model_failure_yield_band')}`",
        f"- dataset_real_model_intake_backlog_status: `{kpis.get('dataset_real_model_intake_backlog_status')}`",
        f"- dataset_real_model_intake_backlog_item_count: `{kpis.get('dataset_real_model_intake_backlog_item_count')}`",
        f"- dataset_real_model_intake_backlog_p0_count: `{kpis.get('dataset_real_model_intake_backlog_p0_count')}`",
        f"- dataset_modelica_moat_readiness_gate_status: `{kpis.get('dataset_modelica_moat_readiness_gate_status')}`",
        f"- dataset_modelica_moat_readiness_score: `{kpis.get('dataset_modelica_moat_readiness_score')}`",
        f"- dataset_modelica_moat_release_recommendation: `{kpis.get('dataset_modelica_moat_release_recommendation')}`",
        f"- dataset_modelica_moat_confidence_level: `{kpis.get('dataset_modelica_moat_confidence_level')}`",
        f"- dataset_modelica_moat_critical_blocker_count: `{kpis.get('dataset_modelica_moat_critical_blocker_count')}`",
        f"- dataset_real_model_license_risk_score: `{kpis.get('dataset_real_model_license_risk_score')}`",
        f"- dataset_real_model_supply_health_status: `{kpis.get('dataset_real_model_supply_health_status')}`",
        f"- dataset_real_model_supply_health_score: `{kpis.get('dataset_real_model_supply_health_score')}`",
        f"- dataset_real_model_supply_gap_count: `{kpis.get('dataset_real_model_supply_gap_count')}`",
        f"- dataset_mutation_recipe_execution_audit_status: `{kpis.get('dataset_mutation_recipe_execution_audit_status')}`",
        f"- dataset_mutation_recipe_execution_coverage_pct: `{kpis.get('dataset_mutation_recipe_execution_coverage_pct')}`",
        f"- dataset_mutation_recipe_missing_count: `{kpis.get('dataset_mutation_recipe_missing_count')}`",
        f"- dataset_modelica_release_candidate_gate_status: `{kpis.get('dataset_modelica_release_candidate_gate_status')}`",
        f"- dataset_modelica_release_candidate_score: `{kpis.get('dataset_modelica_release_candidate_score')}`",
        f"- dataset_modelica_release_candidate_decision: `{kpis.get('dataset_modelica_release_candidate_decision')}`",
        f"- dataset_milestone_checkpoint_status: `{kpis.get('dataset_milestone_checkpoint_status')}`",
        f"- dataset_milestone_checkpoint_score: `{kpis.get('dataset_milestone_checkpoint_score')}`",
        f"- dataset_milestone_checkpoint_decision: `{kpis.get('dataset_milestone_checkpoint_decision')}`",
        f"- dataset_milestone_checkpoint_trend_status: `{kpis.get('dataset_milestone_checkpoint_trend_status')}`",
        f"- dataset_milestone_checkpoint_trend_transition: `{kpis.get('dataset_milestone_checkpoint_trend_transition')}`",
        f"- dataset_milestone_public_brief_status: `{kpis.get('dataset_milestone_public_brief_status')}`",
        f"- dataset_milestone_public_brief_decision: `{kpis.get('dataset_milestone_public_brief_decision')}`",
        f"- dataset_intake_growth_advisor_status: `{kpis.get('dataset_intake_growth_advisor_status')}`",
        f"- dataset_intake_growth_suggested_action: `{kpis.get('dataset_intake_growth_suggested_action')}`",
        f"- dataset_intake_growth_backlog_action_count: `{kpis.get('dataset_intake_growth_backlog_action_count')}`",
        f"- dataset_intake_growth_advisor_history_status: `{kpis.get('dataset_intake_growth_advisor_history_status')}`",
        f"- dataset_intake_growth_advisor_history_latest_action: `{kpis.get('dataset_intake_growth_advisor_history_latest_action')}`",
        f"- dataset_intake_growth_advisor_history_recovery_plan_rate: `{kpis.get('dataset_intake_growth_advisor_history_recovery_plan_rate')}`",
        f"- dataset_intake_growth_advisor_history_trend_status: `{kpis.get('dataset_intake_growth_advisor_history_trend_status')}`",
        f"- dataset_intake_growth_advisor_history_trend_alert_count: `{kpis.get('dataset_intake_growth_advisor_history_trend_alert_count')}`",
        f"- dataset_intake_growth_execution_board_status: `{kpis.get('dataset_intake_growth_execution_board_status')}`",
        f"- dataset_intake_growth_execution_board_execution_score: `{kpis.get('dataset_intake_growth_execution_board_execution_score')}`",
        f"- dataset_intake_growth_execution_board_critical_open_tasks: `{kpis.get('dataset_intake_growth_execution_board_critical_open_tasks')}`",
        f"- dataset_intake_growth_execution_board_projected_weeks_to_target: `{kpis.get('dataset_intake_growth_execution_board_projected_weeks_to_target')}`",
        f"- dataset_intake_growth_execution_board_history_status: `{kpis.get('dataset_intake_growth_execution_board_history_status')}`",
        f"- dataset_intake_growth_execution_board_history_avg_execution_score: `{kpis.get('dataset_intake_growth_execution_board_history_avg_execution_score')}`",
        f"- dataset_intake_growth_execution_board_history_critical_open_tasks_rate: `{kpis.get('dataset_intake_growth_execution_board_history_critical_open_tasks_rate')}`",
        f"- dataset_intake_growth_execution_board_history_trend_status: `{kpis.get('dataset_intake_growth_execution_board_history_trend_status')}`",
        f"- dataset_intake_growth_execution_board_history_trend_alert_count: `{kpis.get('dataset_intake_growth_execution_board_history_trend_alert_count')}`",
        f"- dataset_real_model_intake_portfolio_status: `{kpis.get('dataset_real_model_intake_portfolio_status')}`",
        f"- dataset_real_model_intake_portfolio_total_real_models: `{kpis.get('dataset_real_model_intake_portfolio_total_real_models')}`",
        f"- dataset_real_model_intake_portfolio_large_models: `{kpis.get('dataset_real_model_intake_portfolio_large_models')}`",
        f"- dataset_real_model_intake_portfolio_license_clean_ratio_pct: `{kpis.get('dataset_real_model_intake_portfolio_license_clean_ratio_pct')}`",
        f"- dataset_real_model_intake_portfolio_active_domains_count: `{kpis.get('dataset_real_model_intake_portfolio_active_domains_count')}`",
        f"- dataset_mutation_coverage_depth_status: `{kpis.get('dataset_mutation_coverage_depth_status')}`",
        f"- dataset_mutation_coverage_depth_score: `{kpis.get('dataset_mutation_coverage_depth_score')}`",
        f"- dataset_mutation_coverage_depth_uncovered_cells_count: `{kpis.get('dataset_mutation_coverage_depth_uncovered_cells_count')}`",
        f"- dataset_mutation_coverage_depth_high_risk_gaps_count: `{kpis.get('dataset_mutation_coverage_depth_high_risk_gaps_count')}`",
        f"- dataset_failure_distribution_stability_status: `{kpis.get('dataset_failure_distribution_stability_status')}`",
        f"- dataset_failure_distribution_stability_score: `{kpis.get('dataset_failure_distribution_stability_score')}`",
        f"- dataset_failure_distribution_stability_drift_band: `{kpis.get('dataset_failure_distribution_stability_drift_band')}`",
        f"- dataset_failure_distribution_stability_rare_failure_replay_rate: `{kpis.get('dataset_failure_distribution_stability_rare_failure_replay_rate')}`",
        f"- dataset_failure_distribution_stability_delta_drift: `{kpis.get('dataset_failure_distribution_stability_delta_drift')}`",
        "",
        "## Risks",
        "",
    ]
    risks = summary.get("risks", [])
    if isinstance(risks, list) and risks:
        for r in risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Sources", ""])
    sources = summary.get("sources", {})
    for k, v in sources.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dataset governance snapshot from dataset governance artifacts")
    parser.add_argument("--dataset-pipeline-summary", default=None, help="Path to dataset pipeline summary JSON")
    parser.add_argument("--dataset-history-summary", default=None, help="Path to dataset history summary JSON")
    parser.add_argument("--dataset-history-trend", default=None, help="Path to dataset history trend JSON")
    parser.add_argument("--dataset-governance-summary", default=None, help="Path to dataset governance ledger summary JSON")
    parser.add_argument("--dataset-governance-trend", default=None, help="Path to dataset governance trend JSON")
    parser.add_argument("--dataset-policy-effectiveness", default=None, help="Path to dataset policy effectiveness JSON")
    parser.add_argument("--dataset-strategy-advisor", default=None, help="Path to dataset strategy advisor JSON")
    parser.add_argument(
        "--dataset-strategy-apply-history",
        default=None,
        help="Path to dataset strategy apply history summary JSON",
    )
    parser.add_argument(
        "--dataset-strategy-apply-history-trend",
        default=None,
        help="Path to dataset strategy apply history trend JSON",
    )
    parser.add_argument(
        "--dataset-promotion-history",
        default=None,
        help="Path to dataset promotion candidate history summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-history-trend",
        default=None,
        help="Path to dataset promotion candidate history trend JSON",
    )
    parser.add_argument(
        "--dataset-promotion-apply-history",
        default=None,
        help="Path to dataset promotion apply history summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-apply-history-trend",
        default=None,
        help="Path to dataset promotion apply history trend JSON",
    )
    parser.add_argument(
        "--dataset-promotion-effectiveness",
        default=None,
        help="Path to dataset promotion effectiveness summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-effectiveness-history",
        default=None,
        help="Path to dataset promotion effectiveness history summary JSON",
    )
    parser.add_argument(
        "--dataset-promotion-effectiveness-history-trend",
        default=None,
        help="Path to dataset promotion effectiveness history trend JSON",
    )
    parser.add_argument(
        "--dataset-failure-taxonomy-coverage",
        default=None,
        help="Path to dataset failure taxonomy coverage summary JSON",
    )
    parser.add_argument(
        "--dataset-failure-distribution-benchmark",
        default=None,
        help="Path to dataset failure distribution benchmark summary JSON",
    )
    parser.add_argument(
        "--dataset-model-scale-ladder",
        default=None,
        help="Path to dataset model scale ladder summary JSON",
    )
    parser.add_argument(
        "--dataset-failure-policy-patch-advisor",
        default=None,
        help="Path to dataset failure policy patch advisor JSON",
    )
    parser.add_argument(
        "--dataset-modelica-library-provenance-guard",
        default=None,
        help="Path to dataset modelica library provenance guard summary JSON",
    )
    parser.add_argument(
        "--dataset-large-model-benchmark-pack",
        default=None,
        help="Path to dataset large model benchmark pack summary JSON",
    )
    parser.add_argument(
        "--dataset-mutation-campaign-tracker",
        default=None,
        help="Path to dataset mutation campaign tracker summary JSON",
    )
    parser.add_argument(
        "--dataset-moat-public-scoreboard",
        default=None,
        help="Path to dataset moat public scoreboard summary JSON",
    )
    parser.add_argument(
        "--dataset-real-model-license-compliance",
        default=None,
        help="Path to dataset real model license compliance summary JSON",
    )
    parser.add_argument(
        "--dataset-modelica-mutation-recipe-library",
        default=None,
        help="Path to dataset modelica mutation recipe library summary JSON",
    )
    parser.add_argument(
        "--dataset-real-model-failure-yield",
        default=None,
        help="Path to dataset real model failure yield summary JSON",
    )
    parser.add_argument(
        "--dataset-real-model-intake-backlog",
        default=None,
        help="Path to dataset real model intake backlog summary JSON",
    )
    parser.add_argument(
        "--dataset-modelica-moat-readiness-gate",
        default=None,
        help="Path to dataset modelica moat readiness gate summary JSON",
    )
    parser.add_argument(
        "--dataset-real-model-supply-health",
        default=None,
        help="Path to dataset real model supply health summary JSON",
    )
    parser.add_argument(
        "--dataset-mutation-recipe-execution-audit",
        default=None,
        help="Path to dataset mutation recipe execution audit summary JSON",
    )
    parser.add_argument(
        "--dataset-modelica-release-candidate-gate",
        default=None,
        help="Path to dataset modelica release candidate gate summary JSON",
    )
    parser.add_argument(
        "--dataset-milestone-checkpoint",
        default=None,
        help="Path to dataset milestone checkpoint summary JSON",
    )
    parser.add_argument(
        "--dataset-milestone-checkpoint-trend",
        default=None,
        help="Path to dataset milestone checkpoint trend summary JSON",
    )
    parser.add_argument(
        "--dataset-milestone-public-brief",
        default=None,
        help="Path to dataset milestone public brief JSON",
    )
    parser.add_argument(
        "--dataset-intake-growth-advisor",
        default=None,
        help="Path to dataset intake growth advisor summary JSON",
    )
    parser.add_argument(
        "--dataset-intake-growth-advisor-history",
        default=None,
        help="Path to dataset intake growth advisor history summary JSON",
    )
    parser.add_argument(
        "--dataset-intake-growth-advisor-history-trend",
        default=None,
        help="Path to dataset intake growth advisor history trend summary JSON",
    )
    parser.add_argument(
        "--dataset-intake-growth-execution-board",
        default=None,
        help="Path to dataset intake growth execution board summary JSON",
    )
    parser.add_argument(
        "--dataset-intake-growth-execution-board-history",
        default=None,
        help="Path to dataset intake growth execution board history summary JSON",
    )
    parser.add_argument(
        "--dataset-intake-growth-execution-board-history-trend",
        default=None,
        help="Path to dataset intake growth execution board history trend summary JSON",
    )
    parser.add_argument(
        "--dataset-real-model-intake-portfolio",
        default=None,
        help="Path to dataset real model intake portfolio summary JSON",
    )
    parser.add_argument(
        "--dataset-mutation-coverage-depth",
        default=None,
        help="Path to dataset mutation coverage depth summary JSON",
    )
    parser.add_argument(
        "--dataset-failure-distribution-stability",
        default=None,
        help="Path to dataset failure distribution stability summary JSON",
    )
    parser.add_argument("--out", default="artifacts/dataset_governance_snapshot/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    dataset_pipeline = _load_json(args.dataset_pipeline_summary)
    dataset_history = _load_json(args.dataset_history_summary)
    dataset_history_trend = _load_json(args.dataset_history_trend)
    dataset_governance = _load_json(args.dataset_governance_summary)
    dataset_governance_trend = _load_json(args.dataset_governance_trend)
    effectiveness = _load_json(args.dataset_policy_effectiveness)
    strategy_advisor = _load_json(args.dataset_strategy_advisor)
    strategy_apply_history = _load_json(args.dataset_strategy_apply_history)
    strategy_apply_history_trend = _load_json(args.dataset_strategy_apply_history_trend)
    promotion_history = _load_json(args.dataset_promotion_history)
    promotion_history_trend = _load_json(args.dataset_promotion_history_trend)
    promotion_apply_history = _load_json(args.dataset_promotion_apply_history)
    promotion_apply_history_trend = _load_json(args.dataset_promotion_apply_history_trend)
    promotion_effectiveness = _load_json(args.dataset_promotion_effectiveness)
    promotion_effectiveness_history = _load_json(args.dataset_promotion_effectiveness_history)
    promotion_effectiveness_history_trend = _load_json(args.dataset_promotion_effectiveness_history_trend)
    failure_taxonomy_coverage = _load_json(args.dataset_failure_taxonomy_coverage)
    failure_distribution_benchmark = _load_json(args.dataset_failure_distribution_benchmark)
    model_scale_ladder = _load_json(args.dataset_model_scale_ladder)
    failure_policy_patch_advisor = _load_json(args.dataset_failure_policy_patch_advisor)
    modelica_library_provenance_guard = _load_json(args.dataset_modelica_library_provenance_guard)
    large_model_benchmark_pack = _load_json(args.dataset_large_model_benchmark_pack)
    mutation_campaign_tracker = _load_json(args.dataset_mutation_campaign_tracker)
    moat_public_scoreboard = _load_json(args.dataset_moat_public_scoreboard)
    real_model_license_compliance = _load_json(args.dataset_real_model_license_compliance)
    modelica_mutation_recipe_library = _load_json(args.dataset_modelica_mutation_recipe_library)
    real_model_failure_yield = _load_json(args.dataset_real_model_failure_yield)
    real_model_intake_backlog = _load_json(args.dataset_real_model_intake_backlog)
    modelica_moat_readiness_gate = _load_json(args.dataset_modelica_moat_readiness_gate)
    real_model_supply_health = _load_json(args.dataset_real_model_supply_health)
    mutation_recipe_execution_audit = _load_json(args.dataset_mutation_recipe_execution_audit)
    modelica_release_candidate_gate = _load_json(args.dataset_modelica_release_candidate_gate)
    milestone_checkpoint = _load_json(args.dataset_milestone_checkpoint)
    milestone_checkpoint_trend = _load_json(args.dataset_milestone_checkpoint_trend)
    milestone_public_brief = _load_json(args.dataset_milestone_public_brief)
    intake_growth_advisor = _load_json(args.dataset_intake_growth_advisor)
    intake_growth_advisor_history = _load_json(args.dataset_intake_growth_advisor_history)
    intake_growth_advisor_history_trend = _load_json(args.dataset_intake_growth_advisor_history_trend)
    intake_growth_execution_board = _load_json(args.dataset_intake_growth_execution_board)
    intake_growth_execution_board_history = _load_json(args.dataset_intake_growth_execution_board_history)
    intake_growth_execution_board_history_trend = _load_json(args.dataset_intake_growth_execution_board_history_trend)
    real_model_intake_portfolio = _load_json(args.dataset_real_model_intake_portfolio)
    mutation_coverage_depth = _load_json(args.dataset_mutation_coverage_depth)
    failure_distribution_stability = _load_json(args.dataset_failure_distribution_stability)

    summary = _compute_summary(
        dataset_pipeline,
        dataset_history,
        dataset_history_trend,
        dataset_governance,
        dataset_governance_trend,
        effectiveness,
        strategy_advisor,
        strategy_apply_history,
        strategy_apply_history_trend,
        promotion_history,
        promotion_history_trend,
        promotion_apply_history,
        promotion_apply_history_trend,
        promotion_effectiveness,
        promotion_effectiveness_history,
        promotion_effectiveness_history_trend,
        failure_taxonomy_coverage,
        failure_distribution_benchmark,
        model_scale_ladder,
        failure_policy_patch_advisor,
        modelica_library_provenance_guard,
        large_model_benchmark_pack,
        mutation_campaign_tracker,
        moat_public_scoreboard,
        real_model_license_compliance,
        modelica_mutation_recipe_library,
        real_model_failure_yield,
        real_model_intake_backlog,
        modelica_moat_readiness_gate,
        real_model_supply_health,
        mutation_recipe_execution_audit,
        modelica_release_candidate_gate,
        milestone_checkpoint,
        milestone_checkpoint_trend,
        milestone_public_brief,
        intake_growth_advisor,
        intake_growth_advisor_history,
        intake_growth_advisor_history_trend,
        intake_growth_execution_board,
        intake_growth_execution_board_history,
        intake_growth_execution_board_history_trend,
        real_model_intake_portfolio,
        mutation_coverage_depth,
        failure_distribution_stability,
    )
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["sources"] = {
        "dataset_pipeline_summary_path": args.dataset_pipeline_summary,
        "dataset_history_summary_path": args.dataset_history_summary,
        "dataset_history_trend_path": args.dataset_history_trend,
        "dataset_governance_summary_path": args.dataset_governance_summary,
        "dataset_governance_trend_path": args.dataset_governance_trend,
        "dataset_policy_effectiveness_path": args.dataset_policy_effectiveness,
        "dataset_strategy_advisor_path": args.dataset_strategy_advisor,
        "dataset_strategy_apply_history_path": args.dataset_strategy_apply_history,
        "dataset_strategy_apply_history_trend_path": args.dataset_strategy_apply_history_trend,
        "dataset_promotion_history_path": args.dataset_promotion_history,
        "dataset_promotion_history_trend_path": args.dataset_promotion_history_trend,
        "dataset_promotion_apply_history_path": args.dataset_promotion_apply_history,
        "dataset_promotion_apply_history_trend_path": args.dataset_promotion_apply_history_trend,
        "dataset_promotion_effectiveness_path": args.dataset_promotion_effectiveness,
        "dataset_promotion_effectiveness_history_path": args.dataset_promotion_effectiveness_history,
        "dataset_promotion_effectiveness_history_trend_path": args.dataset_promotion_effectiveness_history_trend,
        "dataset_failure_taxonomy_coverage_path": args.dataset_failure_taxonomy_coverage,
        "dataset_failure_distribution_benchmark_path": args.dataset_failure_distribution_benchmark,
        "dataset_model_scale_ladder_path": args.dataset_model_scale_ladder,
        "dataset_failure_policy_patch_advisor_path": args.dataset_failure_policy_patch_advisor,
        "dataset_modelica_library_provenance_guard_path": args.dataset_modelica_library_provenance_guard,
        "dataset_large_model_benchmark_pack_path": args.dataset_large_model_benchmark_pack,
        "dataset_mutation_campaign_tracker_path": args.dataset_mutation_campaign_tracker,
        "dataset_moat_public_scoreboard_path": args.dataset_moat_public_scoreboard,
        "dataset_real_model_license_compliance_path": args.dataset_real_model_license_compliance,
        "dataset_modelica_mutation_recipe_library_path": args.dataset_modelica_mutation_recipe_library,
        "dataset_real_model_failure_yield_path": args.dataset_real_model_failure_yield,
        "dataset_real_model_intake_backlog_path": args.dataset_real_model_intake_backlog,
        "dataset_modelica_moat_readiness_gate_path": args.dataset_modelica_moat_readiness_gate,
        "dataset_real_model_supply_health_path": args.dataset_real_model_supply_health,
        "dataset_mutation_recipe_execution_audit_path": args.dataset_mutation_recipe_execution_audit,
        "dataset_modelica_release_candidate_gate_path": args.dataset_modelica_release_candidate_gate,
        "dataset_milestone_checkpoint_path": args.dataset_milestone_checkpoint,
        "dataset_milestone_checkpoint_trend_path": args.dataset_milestone_checkpoint_trend,
        "dataset_milestone_public_brief_path": args.dataset_milestone_public_brief,
        "dataset_intake_growth_advisor_path": args.dataset_intake_growth_advisor,
        "dataset_intake_growth_advisor_history_path": args.dataset_intake_growth_advisor_history,
        "dataset_intake_growth_advisor_history_trend_path": args.dataset_intake_growth_advisor_history_trend,
        "dataset_intake_growth_execution_board_path": args.dataset_intake_growth_execution_board,
        "dataset_intake_growth_execution_board_history_path": args.dataset_intake_growth_execution_board_history,
        "dataset_intake_growth_execution_board_history_trend_path": args.dataset_intake_growth_execution_board_history_trend,
        "dataset_real_model_intake_portfolio_path": args.dataset_real_model_intake_portfolio,
        "dataset_mutation_coverage_depth_path": args.dataset_mutation_coverage_depth,
        "dataset_failure_distribution_stability_path": args.dataset_failure_distribution_stability,
    }

    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "risks": summary.get("risks", [])}))

    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
