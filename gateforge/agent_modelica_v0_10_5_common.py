from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_5"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_handoff_integrity_current"
DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_real_origin_threshold_input_table_current"
)
DEFAULT_THRESHOLD_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_first_real_origin_threshold_pack_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_closeout_current"

DEFAULT_V104_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_closeout_current" / "summary.json"
DEFAULT_V104_CHARACTERIZATION_PATH = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_v0_10_4_real_origin_workflow_profile_characterization_current"
    / "summary.json"
)

MIN_PROFILE_RUN_COUNT = 3
MAX_UNEXPLAINED_CASE_FLIPS = 1

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR",
    "DEFAULT_THRESHOLD_PACK_OUT_DIR",
    "DEFAULT_V104_CHARACTERIZATION_PATH",
    "DEFAULT_V104_CLOSEOUT_PATH",
    "MAX_UNEXPLAINED_CASE_FLIPS",
    "MIN_PROFILE_RUN_COUNT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
