from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_0"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_governance_pack_current"
DEFAULT_DEPTH_PROBE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_depth_probe_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_closeout_current"

DEFAULT_V080_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_closeout_current" / "summary.json"
DEFAULT_V081_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_closeout_current" / "summary.json"
DEFAULT_V086_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_6_closeout_current" / "summary.json"

PRIORITY_BARRIERS = (
    "goal_artifact_missing_after_surface_fix",
    "dispatch_or_policy_limited_unresolved",
    "workflow_spillover_unresolved",
)

CONTEXT_NATURALNESS_RISK_VALUES = ("low", "medium", "high")
WORKING_MINIMUM_PER_PRIORITY_BARRIER = 5
DEGRADED_MINIMUM_PER_PRIORITY_BARRIER = 3


__all__ = [
    "CONTEXT_NATURALNESS_RISK_VALUES",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DEPTH_PROBE_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V080_CLOSEOUT_PATH",
    "DEFAULT_V081_CLOSEOUT_PATH",
    "DEFAULT_V086_CLOSEOUT_PATH",
    "DEGRADED_MINIMUM_PER_PRIORITY_BARRIER",
    "PRIORITY_BARRIERS",
    "SCHEMA_PREFIX",
    "WORKING_MINIMUM_PER_PRIORITY_BARRIER",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
