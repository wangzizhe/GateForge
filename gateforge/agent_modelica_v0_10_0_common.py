from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_0"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_0_governance_pack_current"
DEFAULT_DEPTH_PROBE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_0_depth_probe_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_0_closeout_current"

DEFAULT_V097_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_7_closeout_current" / "summary.json"

SOURCE_ORIGIN_CLASSES = ("real_origin", "semi_real_origin", "workflow_proximal_proxy")
REAL_ORIGIN_DISTANCE_VALUES = ("near", "medium", "far")
PROXY_LEAKAGE_RISK_LEVELS = ("low", "medium", "high")

PROMOTED_MAINLINE_MIN_COUNT = 12
PROMOTED_MAINLINE_MIN_FAMILY_COUNT = 3
PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT = 50.0

DEGRADED_MAINLINE_MIN_COUNT = 6
DEGRADED_MAINLINE_MIN_FAMILY_COUNT = 2


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DEPTH_PROBE_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V097_CLOSEOUT_PATH",
    "DEGRADED_MAINLINE_MIN_COUNT",
    "DEGRADED_MAINLINE_MIN_FAMILY_COUNT",
    "PROMOTED_MAINLINE_MIN_COUNT",
    "PROMOTED_MAINLINE_MIN_FAMILY_COUNT",
    "PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT",
    "PROXY_LEAKAGE_RISK_LEVELS",
    "REAL_ORIGIN_DISTANCE_VALUES",
    "SCHEMA_PREFIX",
    "SOURCE_ORIGIN_CLASSES",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
