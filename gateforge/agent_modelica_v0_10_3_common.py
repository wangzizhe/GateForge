from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_3"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_handoff_integrity_current"
DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_real_origin_substrate_builder_current"
DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_real_origin_substrate_admission_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_closeout_current"

DEFAULT_V102_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_closeout_current" / "summary.json"
DEFAULT_V102_POOL_DELTA_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_pool_delta_current" / "summary.json"

READY_MIN_SUBSTRATE_SIZE = 12
READY_MIN_SOURCE_COUNT = 4
READY_MIN_FAMILY_COUNT = 3
READY_MAX_SINGLE_SOURCE_SHARE_PCT = 50.0


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR",
    "DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR",
    "DEFAULT_V102_CLOSEOUT_PATH",
    "DEFAULT_V102_POOL_DELTA_PATH",
    "READY_MAX_SINGLE_SOURCE_SHARE_PCT",
    "READY_MIN_FAMILY_COUNT",
    "READY_MIN_SOURCE_COUNT",
    "READY_MIN_SUBSTRATE_SIZE",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
