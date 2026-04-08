from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_7_7_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_0"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_handoff_integrity_current"
)
DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_workflow_proximal_substrate_current"
)
DEFAULT_PILOT_PROFILE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_pilot_workflow_profile_current"
)
DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_workflow_substrate_admission_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_closeout_current"
)

DEFAULT_V077_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_7_7_closeout_current" / "summary.json"
)

TASK_COUNT_MIN = 8
AUDIT_PROMOTED_MIN = 80.0
AUDIT_DEGRADED_MIN = 70.0
GOAL_SPECIFIC_RATE_PROMOTED_MIN = 50.0
GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN = 3
LEGACY_BUCKET_MAPPING_RATE_MIN = 70.0
SPILLOVER_SHARE_MAX = 35.0
UNCLASSIFIED_PENDING_MAX = 3

GOAL_SPECIFIC_CHECK_TYPES = {
    "named_result_invariant_pass",
    "expected_goal_artifact_present",
}

ALLOWED_CHECK_TYPES = {
    "check_model_pass",
    "simulate_pass",
    *GOAL_SPECIFIC_CHECK_TYPES,
}


__all__ = [
    "ALLOWED_CHECK_TYPES",
    "AUDIT_DEGRADED_MIN",
    "AUDIT_PROMOTED_MIN",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PILOT_PROFILE_OUT_DIR",
    "DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR",
    "DEFAULT_V077_CLOSEOUT_PATH",
    "DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR",
    "GOAL_SPECIFIC_CHECK_TYPES",
    "GOAL_SPECIFIC_RATE_PROMOTED_MIN",
    "GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN",
    "LEGACY_BUCKET_MAPPING_RATE_MIN",
    "SCHEMA_PREFIX",
    "SPILLOVER_SHARE_MAX",
    "TASK_COUNT_MIN",
    "UNCLASSIFIED_PENDING_MAX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
