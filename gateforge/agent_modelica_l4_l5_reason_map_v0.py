from __future__ import annotations


SCHEMA_VERSION = "agent_modelica_l4_l5_reason_map_v0"
ALLOWED_L4_PRIMARY_REASONS = {
    "none",
    "hard_checks_pass",
    "max_rounds_reached",
    "time_budget_exceeded",
    "no_progress_window",
    "action_plan_failed",
    "apply_failed",
    "llm_fallback_exhausted",
}
ALLOWED_WEEKLY_RECOMMENDATION_REASONS = {
    "none",
    "insufficient_history",
    "insufficient_consecutive_history",
    "two_week_consecutive_pass",
    "threshold_not_met",
    "reason_enum_unknown",
    "run_summary_missing",
    "run_results_missing",
    "l3_quality_summary_missing",
    "l4_ab_compare_summary_missing",
    "attempts_missing",
    "delta_success_at_k_below_threshold",
    "absolute_success_below_threshold",
    "non_regression_failed",
    "physics_fail_rate_worsened_beyond_threshold",
    "regression_fail_rate_worsened_beyond_threshold",
    "infra_failure_count_not_zero",
    "l3_parse_coverage_below_threshold",
    "l3_type_match_rate_below_threshold",
    "l3_stage_match_rate_below_threshold",
    "l3_diagnostic_gate_not_pass",
    "l3_diagnostic_gate_needs_review",
    "max_rounds_reached",
    "time_budget_exceeded",
    "no_progress_window",
    "action_plan_failed",
    "apply_failed",
    "llm_fallback_exhausted",
}


def normalize_l4_primary_reason_v0(reason: str | None) -> str:
    text = str(reason or "").strip()
    if text in ALLOWED_L4_PRIMARY_REASONS:
        return text
    return "reason_enum_unknown"


def map_l4_to_weekly_recommendation_reason_v0(reason: str | None) -> str:
    normalized = normalize_l4_primary_reason_v0(reason)
    if normalized in {"none", "hard_checks_pass"}:
        return "threshold_not_met"
    if normalized in ALLOWED_WEEKLY_RECOMMENDATION_REASONS:
        return normalized
    return "reason_enum_unknown"
