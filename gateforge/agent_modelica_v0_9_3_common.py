from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text
from .agent_modelica_v0_8_1_common import goal_specific_check_mode, outcome_sort_key, range_pct
from .agent_modelica_v0_9_0_common import PRIORITY_BARRIERS


SCHEMA_PREFIX = "agent_modelica_v0_9_3"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_handoff_integrity_current"
DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_expanded_profile_replay_pack_current"
)
DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_expanded_workflow_profile_characterization_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_closeout_current"

DEFAULT_V092_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_closeout_current" / "summary.json"
DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_expanded_substrate_builder_current" / "summary.json"
)

PROFILE_RUN_COUNT = 3
MIN_EXPANDED_SUBSTRATE_SIZE = 18
MIN_READY_BARRIER_COUNT = 5
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
    "DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V092_CLOSEOUT_PATH",
    "DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH",
    "KNOWN_PILOT_OUTCOMES",
    "MAX_UNEXPLAINED_CASE_FLIPS",
    "MIN_EXPANDED_SUBSTRATE_SIZE",
    "MIN_READY_BARRIER_COUNT",
    "NON_SUCCESS_OUTCOMES",
    "PRIORITY_BARRIERS",
    "PROFILE_RUN_COUNT",
    "SCHEMA_PREFIX",
    "goal_specific_check_mode",
    "load_json",
    "now_utc",
    "outcome_sort_key",
    "range_pct",
    "write_json",
    "write_text",
]
