from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_11_4"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_handoff_integrity_current"
DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_product_gap_threshold_input_table_current"
)
DEFAULT_THRESHOLD_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_product_gap_threshold_pack_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_closeout_current"

DEFAULT_V113_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_closeout_current" / "summary.json"
DEFAULT_V113_CHARACTERIZATION_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_product_gap_profile_characterization_current" / "summary.json"
)

MIN_PROFILE_RUN_COUNT = 3
DEFAULT_PRODUCT_GAP_CASE_COUNT = 12

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_THRESHOLD_INPUT_TABLE_OUT_DIR",
    "DEFAULT_THRESHOLD_PACK_OUT_DIR",
    "DEFAULT_V113_CHARACTERIZATION_PATH",
    "DEFAULT_V113_CLOSEOUT_PATH",
    "DEFAULT_PRODUCT_GAP_CASE_COUNT",
    "MIN_PROFILE_RUN_COUNT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
