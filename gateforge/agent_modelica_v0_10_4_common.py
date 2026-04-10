from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text
from .agent_modelica_v0_8_1_common import outcome_sort_key, range_pct


SCHEMA_PREFIX = "agent_modelica_v0_10_4"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_handoff_integrity_current"
DEFAULT_REAL_ORIGIN_PROFILE_REPLAY_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_real_origin_profile_replay_pack_current"
)
DEFAULT_REAL_ORIGIN_PROFILE_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_real_origin_workflow_profile_characterization_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_closeout_current"

DEFAULT_V103_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_closeout_current" / "summary.json"
DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_real_origin_substrate_builder_current" / "summary.json"
)

PROFILE_RUN_COUNT = 3
MIN_REAL_ORIGIN_SUBSTRATE_SIZE = 12
MIN_REAL_ORIGIN_SOURCE_COUNT = 4
MAX_UNEXPLAINED_CASE_FLIPS = 1

KNOWN_PILOT_OUTCOMES = (
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
    "DEFAULT_REAL_ORIGIN_PROFILE_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_REAL_ORIGIN_PROFILE_REPLAY_PACK_OUT_DIR",
    "DEFAULT_V103_CLOSEOUT_PATH",
    "DEFAULT_V103_REAL_ORIGIN_SUBSTRATE_BUILDER_PATH",
    "KNOWN_PILOT_OUTCOMES",
    "MAX_UNEXPLAINED_CASE_FLIPS",
    "MIN_REAL_ORIGIN_SOURCE_COUNT",
    "MIN_REAL_ORIGIN_SUBSTRATE_SIZE",
    "NON_SUCCESS_OUTCOMES",
    "PROFILE_RUN_COUNT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "outcome_sort_key",
    "range_pct",
    "write_json",
    "write_text",
]
