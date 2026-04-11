from __future__ import annotations

from .agent_modelica_v0_10_4_common import outcome_sort_key, range_pct
from .agent_modelica_v0_11_2_common import (
    DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR as DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR,
    DEFAULT_V111_CLOSEOUT_PATH,
    PENDING_PROFILE_RUN,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_0_common import REPO_ROOT


SCHEMA_PREFIX = "agent_modelica_v0_11_3"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_handoff_integrity_current"
DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_product_gap_profile_replay_pack_current"
)
DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_product_gap_profile_characterization_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_closeout_current"

DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH = DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"
DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_SIZE = 12

EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_HANDOFF_MODE = "characterize_first_product_gap_profile"

PROFILE_RUN_COUNT = 3
MAX_UNEXPLAINED_CASE_FLIPS = 1

KNOWN_PROFILE_OUTCOMES = (
    "goal_level_resolved",
    "surface_fix_only",
    "goal_misaligned",
    "unresolved",
)

NON_SUCCESS_OUTCOMES = (
    "surface_fix_only",
    "goal_misaligned",
    "unresolved",
)


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PRODUCT_GAP_PROFILE_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_PRODUCT_GAP_PROFILE_REPLAY_PACK_OUT_DIR",
    "DEFAULT_V111_CLOSEOUT_PATH",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH",
    "DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_SIZE",
    "EXPECTED_V112_HANDOFF_MODE",
    "EXPECTED_V112_VERSION_DECISION",
    "KNOWN_PROFILE_OUTCOMES",
    "MAX_UNEXPLAINED_CASE_FLIPS",
    "NON_SUCCESS_OUTCOMES",
    "PENDING_PROFILE_RUN",
    "PROFILE_RUN_COUNT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "outcome_sort_key",
    "range_pct",
    "write_json",
    "write_text",
]
