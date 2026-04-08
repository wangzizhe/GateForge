from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_1"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_handoff_integrity_current"
)
DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_profile_replay_pack_current"
)
DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_workflow_profile_characterization_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_closeout_current"
)

DEFAULT_V080_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_closeout_current" / "summary.json"
)
DEFAULT_V080_SUBSTRATE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_workflow_proximal_substrate_current" / "summary.json"
)
DEFAULT_V080_PILOT_PROFILE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_pilot_workflow_profile_current" / "summary.json"
)

PROMOTED_PROFILE_RUN_COUNT_MIN = 3
DEGRADED_PROFILE_RUN_COUNT_MIN = 2
PROMOTED_WORKFLOW_RESOLUTION_RANGE_MAX = 10.0
DEGRADED_WORKFLOW_RESOLUTION_RANGE_MAX = 20.0
PROMOTED_GOAL_ALIGNMENT_RANGE_MAX = 15.0
DEGRADED_GOAL_ALIGNMENT_RANGE_MAX = 25.0
PROMOTED_CASE_CONSISTENCY_MIN = 80.0
DEGRADED_CASE_CONSISTENCY_MIN = 70.0


def range_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(max(values) - min(values), 1)


def outcome_sort_key(outcome: str) -> int:
    order = {
        "goal_level_resolved": 0,
        "surface_fix_only": 1,
        "goal_misaligned": 2,
        "unresolved": 3,
    }
    return order.get(outcome, 99)


def goal_specific_check_mode(checks: list[dict]) -> str:
    check_types = {
        str(check.get("type") or "").strip()
        for check in checks
        if isinstance(check, dict)
    }
    has_invariant = "named_result_invariant_pass" in check_types
    has_artifact = "expected_goal_artifact_present" in check_types
    if has_invariant and has_artifact:
        return "mixed"
    if has_artifact:
        return "artifact_only"
    if has_invariant:
        return "invariant_only"
    return "none"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR",
    "DEFAULT_V080_CLOSEOUT_PATH",
    "DEFAULT_V080_PILOT_PROFILE_PATH",
    "DEFAULT_V080_SUBSTRATE_PATH",
    "DEGRADED_CASE_CONSISTENCY_MIN",
    "DEGRADED_GOAL_ALIGNMENT_RANGE_MAX",
    "DEGRADED_PROFILE_RUN_COUNT_MIN",
    "DEGRADED_WORKFLOW_RESOLUTION_RANGE_MAX",
    "PROMOTED_CASE_CONSISTENCY_MIN",
    "PROMOTED_GOAL_ALIGNMENT_RANGE_MAX",
    "PROMOTED_PROFILE_RUN_COUNT_MIN",
    "PROMOTED_WORKFLOW_RESOLUTION_RANGE_MAX",
    "SCHEMA_PREFIX",
    "goal_specific_check_mode",
    "load_json",
    "now_utc",
    "outcome_sort_key",
    "range_pct",
    "write_json",
    "write_text",
]
