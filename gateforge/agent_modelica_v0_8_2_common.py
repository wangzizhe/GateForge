from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_handoff_integrity_current"
)
DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_threshold_input_table_current"
)
DEFAULT_THRESHOLD_FREEZE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_threshold_freeze_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_closeout_current"
)

DEFAULT_V081_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_closeout_current" / "summary.json"
)

SUPPORTED_THRESHOLD_PACK = {
    "primary_workflow_metrics": {
        "workflow_resolution_rate_pct_min": 50.0,
        "goal_alignment_rate_pct_min": 70.0,
        "surface_fix_only_rate_pct_max": 20.0,
        "unresolved_rate_pct_max": 30.0,
    },
    "barrier_sidecar_metrics": {
        "workflow_spillover_share_pct_max": 20.0,
        "dispatch_or_policy_limited_share_pct_max": 20.0,
        "goal_artifact_missing_after_surface_fix_share_pct_max": 20.0,
        "profile_barrier_unclassified_count_max": 0,
    },
    "interpretability_safeguards": {
        "barrier_label_coverage_rate_pct_min": 100.0,
        "surface_fix_only_explained_rate_pct_min": 100.0,
        "unresolved_explained_rate_pct_min": 100.0,
        "legacy_bucket_mapping_rate_pct_min": 80.0,
    },
    "repeatability_preconditions": {
        "profile_run_count_min": 3,
        "workflow_resolution_rate_range_pct_max": 10.0,
        "goal_alignment_rate_range_pct_max": 15.0,
        "per_case_outcome_consistency_rate_pct_min": 80.0,
    },
}

PARTIAL_THRESHOLD_PACK = {
    "primary_workflow_metrics": {
        "workflow_resolution_rate_pct_min": 40.0,
        "goal_alignment_rate_pct_min": 60.0,
        "surface_fix_only_rate_pct_max": 30.0,
        "unresolved_rate_pct_max": 50.0,
    },
    "barrier_sidecar_metrics": {
        "workflow_spillover_share_pct_max": 30.0,
        "dispatch_or_policy_limited_share_pct_max": 30.0,
        "goal_artifact_missing_after_surface_fix_share_pct_max": 30.0,
        "profile_barrier_unclassified_count_max": 1,
    },
    "interpretability_safeguards": {
        "barrier_label_coverage_rate_pct_min": 100.0,
        "surface_fix_only_explained_rate_pct_min": 100.0,
        "unresolved_explained_rate_pct_min": 100.0,
        "legacy_bucket_mapping_rate_pct_min": 70.0,
    },
    "repeatability_preconditions": {
        "profile_run_count_min": 2,
        "workflow_resolution_rate_range_pct_max": 20.0,
        "goal_alignment_rate_range_pct_max": 25.0,
        "per_case_outcome_consistency_rate_pct_min": 70.0,
    },
}

FALLBACK_RULE_SUMMARY = {
    "fallback_trigger_semantics": [
        "workflow_resolved_core_too_low",
        "workflow_spillover_too_high",
        "interpretability_guard_failed",
        "repeatability_precondition_failed",
    ]
}


def share_pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total * 100.0, 1)


def count_from_pct(pct: float, total: int) -> str:
    if total <= 0:
        return "0/0"
    rounded = round(pct * total / 100.0)
    return f"{int(rounded)}/{int(total)}"


def metric_meets_floor(value: float, floor: float) -> bool:
    return float(value) >= float(floor)


def metric_within_ceiling(value: float, ceiling: float) -> bool:
    return float(value) <= float(ceiling)


def evaluate_rule_pack(metrics: dict, pack: dict) -> bool:
    primary = pack["primary_workflow_metrics"]
    barrier = pack["barrier_sidecar_metrics"]
    interpret = pack["interpretability_safeguards"]
    repeat = pack["repeatability_preconditions"]
    return all(
        [
            metric_meets_floor(
                metrics["workflow_resolution_rate_pct"],
                primary["workflow_resolution_rate_pct_min"],
            ),
            metric_meets_floor(
                metrics["goal_alignment_rate_pct"],
                primary["goal_alignment_rate_pct_min"],
            ),
            metric_within_ceiling(
                metrics["surface_fix_only_rate_pct"],
                primary["surface_fix_only_rate_pct_max"],
            ),
            metric_within_ceiling(
                metrics["unresolved_rate_pct"],
                primary["unresolved_rate_pct_max"],
            ),
            metric_within_ceiling(
                metrics["workflow_spillover_share_pct"],
                barrier["workflow_spillover_share_pct_max"],
            ),
            metric_within_ceiling(
                metrics["dispatch_or_policy_limited_share_pct"],
                barrier["dispatch_or_policy_limited_share_pct_max"],
            ),
            metric_within_ceiling(
                metrics["goal_artifact_missing_after_surface_fix_share_pct"],
                barrier["goal_artifact_missing_after_surface_fix_share_pct_max"],
            ),
            int(metrics["profile_barrier_unclassified_count"])
            <= int(barrier["profile_barrier_unclassified_count_max"]),
            metric_meets_floor(
                metrics["barrier_label_coverage_rate_pct"],
                interpret["barrier_label_coverage_rate_pct_min"],
            ),
            metric_meets_floor(
                metrics["surface_fix_only_explained_rate_pct"],
                interpret["surface_fix_only_explained_rate_pct_min"],
            ),
            metric_meets_floor(
                metrics["unresolved_explained_rate_pct"],
                interpret["unresolved_explained_rate_pct_min"],
            ),
            metric_meets_floor(
                metrics["legacy_bucket_mapping_rate_pct"],
                interpret["legacy_bucket_mapping_rate_pct_min"],
            ),
            int(metrics["profile_run_count"]) >= int(repeat["profile_run_count_min"]),
            metric_within_ceiling(
                metrics["workflow_resolution_rate_range_pct"],
                repeat["workflow_resolution_rate_range_pct_max"],
            ),
            metric_within_ceiling(
                metrics["goal_alignment_rate_range_pct"],
                repeat["goal_alignment_rate_range_pct_max"],
            ),
            metric_meets_floor(
                metrics["per_case_outcome_consistency_rate_pct"],
                repeat["per_case_outcome_consistency_rate_pct_min"],
            ),
        ]
    )


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_THRESHOLD_FREEZE_OUT_DIR",
    "DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR",
    "DEFAULT_V081_CLOSEOUT_PATH",
    "FALLBACK_RULE_SUMMARY",
    "PARTIAL_THRESHOLD_PACK",
    "SCHEMA_PREFIX",
    "SUPPORTED_THRESHOLD_PACK",
    "count_from_pct",
    "evaluate_rule_pack",
    "load_json",
    "metric_meets_floor",
    "metric_within_ceiling",
    "now_utc",
    "share_pct",
    "write_json",
    "write_text",
]
