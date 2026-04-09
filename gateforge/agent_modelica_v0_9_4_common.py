from __future__ import annotations

import math

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_4"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_handoff_integrity_current"
DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_threshold_input_table_current"
)
DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_expanded_threshold_pack_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_closeout_current"

DEFAULT_V093_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_closeout_current" / "summary.json"

FROZEN_TASK_COUNT = 19
PROFILE_RUN_COUNT_MIN = 3
UNEXPLAINED_CASE_FLIP_COUNT_MAX = 1
PER_CASE_CONSISTENCY_RATE_PCT_MIN = 95.0
WORKFLOW_RATE_RANGE_PCT_MAX = 0.0
GOAL_ALIGNMENT_RATE_RANGE_PCT_MAX = 0.0

SUPPORTED_THRESHOLD_PACK = {
    "primary_workflow_metrics": {
        "workflow_resolution_case_count_min": 6,
        "goal_alignment_case_count_min": 11,
        "surface_fix_only_case_count_max": 5,
        "unresolved_case_count_max": 8,
    },
    "barrier_sidecar_metrics": {
        "workflow_spillover_case_count_max": 4,
        "dispatch_or_policy_limited_case_count_max": 5,
        "goal_artifact_missing_after_surface_fix_case_count_max": 5,
        "profile_barrier_unclassified_count_max": 0,
    },
    "interpretability_safeguards": {
        "barrier_label_coverage_rate_pct_min": 100.0,
        "surface_fix_only_explained_rate_pct_min": 100.0,
        "unresolved_explained_rate_pct_min": 100.0,
    },
    "repeatability_preconditions": {
        "profile_run_count_min": PROFILE_RUN_COUNT_MIN,
        "unexplained_case_flip_count_max": UNEXPLAINED_CASE_FLIP_COUNT_MAX,
        "per_case_outcome_consistency_rate_pct_min": PER_CASE_CONSISTENCY_RATE_PCT_MIN,
    },
    "execution_posture": {
        "allowed_execution_source": "frozen_expanded_substrate_deterministic_replay",
        "scope_note": (
            "This threshold pack is frozen for evidence compatible with the v0.9.3 "
            "expanded-profile deterministic replay posture, not for live-executor robustness or product readiness."
        ),
    },
}

PARTIAL_THRESHOLD_PACK = {
    "primary_workflow_metrics": {
        "workflow_resolution_case_count_min": 4,
        "goal_alignment_case_count_min": 9,
        "surface_fix_only_case_count_max": 6,
        "unresolved_case_count_max": 10,
    },
    "barrier_sidecar_metrics": {
        "workflow_spillover_case_count_max": 5,
        "dispatch_or_policy_limited_case_count_max": 5,
        "goal_artifact_missing_after_surface_fix_case_count_max": 5,
        "profile_barrier_unclassified_count_max": 0,
    },
    "interpretability_safeguards": {
        "barrier_label_coverage_rate_pct_min": 100.0,
        "surface_fix_only_explained_rate_pct_min": 100.0,
        "unresolved_explained_rate_pct_min": 100.0,
    },
    "repeatability_preconditions": {
        "profile_run_count_min": PROFILE_RUN_COUNT_MIN,
        "unexplained_case_flip_count_max": UNEXPLAINED_CASE_FLIP_COUNT_MAX,
        "per_case_outcome_consistency_rate_pct_min": PER_CASE_CONSISTENCY_RATE_PCT_MIN,
    },
    "execution_posture": {
        "allowed_execution_source": "frozen_expanded_substrate_deterministic_replay",
        "scope_note": (
            "This threshold pack is frozen for evidence compatible with the v0.9.3 "
            "expanded-profile deterministic replay posture, not for live-executor robustness or product readiness."
        ),
    },
}

FALLBACK_RULE_SUMMARY = {
    "fallback_trigger_semantics": [
        "workflow_resolved_core_too_low_for_interpretable_band",
        "goal_alignment_core_too_low_for_interpretable_band",
        "barrier_explainability_guard_failed",
        "repeatability_precondition_failed",
        "execution_posture_semantics_mismatch",
    ]
}


def share_pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total * 100.0, 1)


def pct_from_case_count(case_count: int, total: int) -> float:
    return share_pct(case_count, total)


def integer_safe_display(case_count: int, total: int) -> str:
    return f"{int(case_count)}/{int(total)} ({pct_from_case_count(case_count, total):.1f}%)"


def pct_to_case_count(pct: float, total: int) -> int:
    return int(round(float(pct) * total / 100.0))


def _meets_thresholds(metrics: dict, pack: dict) -> bool:
    primary = pack["primary_workflow_metrics"]
    barrier = pack["barrier_sidecar_metrics"]
    interpret = pack["interpretability_safeguards"]
    repeat = pack["repeatability_preconditions"]
    posture = pack["execution_posture"]
    return all(
        [
            int(metrics["workflow_resolution_case_count"]) >= int(primary["workflow_resolution_case_count_min"]),
            int(metrics["goal_alignment_case_count"]) >= int(primary["goal_alignment_case_count_min"]),
            int(metrics["surface_fix_only_case_count"]) <= int(primary["surface_fix_only_case_count_max"]),
            int(metrics["unresolved_case_count"]) <= int(primary["unresolved_case_count_max"]),
            int(metrics["workflow_spillover_case_count"]) <= int(barrier["workflow_spillover_case_count_max"]),
            int(metrics["dispatch_or_policy_limited_case_count"]) <= int(
                barrier["dispatch_or_policy_limited_case_count_max"]
            ),
            int(metrics["goal_artifact_missing_after_surface_fix_case_count"]) <= int(
                barrier["goal_artifact_missing_after_surface_fix_case_count_max"]
            ),
            int(metrics["profile_barrier_unclassified_count"]) <= int(
                barrier["profile_barrier_unclassified_count_max"]
            ),
            float(metrics["barrier_label_coverage_rate_pct"]) >= float(
                interpret["barrier_label_coverage_rate_pct_min"]
            ),
            float(metrics["surface_fix_only_explained_rate_pct"]) >= float(
                interpret["surface_fix_only_explained_rate_pct_min"]
            ),
            float(metrics["unresolved_explained_rate_pct"]) >= float(
                interpret["unresolved_explained_rate_pct_min"]
            ),
            int(metrics["profile_run_count"]) >= int(repeat["profile_run_count_min"]),
            int(metrics["unexplained_case_flip_count"]) <= int(repeat["unexplained_case_flip_count_max"]),
            float(metrics["per_case_outcome_consistency_rate_pct"]) >= float(
                repeat["per_case_outcome_consistency_rate_pct_min"]
            ),
            str(metrics["execution_source"] or "") == str(posture["allowed_execution_source"]),
        ]
    )


def classify_baseline_against_pack(metrics: dict, *, supported_pack: dict, partial_pack: dict) -> str:
    if _meets_thresholds(metrics, supported_pack):
        return "expanded_workflow_readiness_supported"
    if _meets_thresholds(metrics, partial_pack):
        return "expanded_workflow_readiness_partial_but_interpretable"
    return "fallback_to_profile_clarification_or_expansion_needed"


def ratio_is_integer_safe(case_count: int, total: int, pct: float) -> bool:
    if total <= 0:
        return False
    return math.isclose(pct_from_case_count(case_count, total), float(pct), abs_tol=0.05)


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_EXPANDED_THRESHOLD_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR",
    "DEFAULT_V093_CLOSEOUT_PATH",
    "FALLBACK_RULE_SUMMARY",
    "FROZEN_TASK_COUNT",
    "GOAL_ALIGNMENT_RATE_RANGE_PCT_MAX",
    "PARTIAL_THRESHOLD_PACK",
    "PER_CASE_CONSISTENCY_RATE_PCT_MIN",
    "PROFILE_RUN_COUNT_MIN",
    "SCHEMA_PREFIX",
    "SUPPORTED_THRESHOLD_PACK",
    "UNEXPLAINED_CASE_FLIP_COUNT_MAX",
    "WORKFLOW_RATE_RANGE_PCT_MAX",
    "classify_baseline_against_pack",
    "integer_safe_display",
    "load_json",
    "now_utc",
    "pct_from_case_count",
    "pct_to_case_count",
    "ratio_is_integer_safe",
    "share_pct",
    "write_json",
    "write_text",
]
