from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_handoff_integrity_current"
DEFAULT_SOURCE_ADMISSION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_source_admission_current"
DEFAULT_POOL_DELTA_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_pool_delta_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_closeout_current"

DEFAULT_V101_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_1_closeout_current" / "summary.json"
DEFAULT_V101_POOL_DELTA_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_1_pool_delta_current" / "summary.json"

PROMOTED_MAINLINE_MIN_COUNT = 12
PROMOTED_MAINLINE_MIN_FAMILY_COUNT = 3
PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT = 50.0

DEGRADED_MAINLINE_MIN_COUNT = 11
DEGRADED_MAINLINE_MIN_FAMILY_COUNT = 3
MIN_NEW_REAL_SOURCE_MAINLINE_YIELD = 2


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_POOL_DELTA_OUT_DIR",
    "DEFAULT_SOURCE_ADMISSION_OUT_DIR",
    "DEFAULT_V101_CLOSEOUT_PATH",
    "DEFAULT_V101_POOL_DELTA_PATH",
    "DEGRADED_MAINLINE_MIN_COUNT",
    "DEGRADED_MAINLINE_MIN_FAMILY_COUNT",
    "MIN_NEW_REAL_SOURCE_MAINLINE_YIELD",
    "PROMOTED_MAINLINE_MIN_COUNT",
    "PROMOTED_MAINLINE_MIN_FAMILY_COUNT",
    "PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
