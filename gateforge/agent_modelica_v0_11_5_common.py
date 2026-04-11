from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_11_5"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_handoff_integrity_current"
DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_product_gap_adjudication_input_table_current"
)
DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_first_product_gap_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current"

DEFAULT_V114_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_closeout_current" / "summary.json"
DEFAULT_V114_THRESHOLD_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_product_gap_threshold_pack_current" / "summary.json"
)
DEFAULT_V113_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_closeout_current" / "summary.json"

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_FIRST_PRODUCT_GAP_ADJUDICATION_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PRODUCT_GAP_ADJUDICATION_INPUT_TABLE_OUT_DIR",
    "DEFAULT_V113_CLOSEOUT_PATH",
    "DEFAULT_V114_CLOSEOUT_PATH",
    "DEFAULT_V114_THRESHOLD_PACK_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
