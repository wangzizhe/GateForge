from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_handoff_integrity_current"
DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_expanded_substrate_builder_current"
)
DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_expanded_substrate_admission_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_closeout_current"

DEFAULT_V091_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_closeout_current" / "summary.json"
DEFAULT_V091_POOL_DELTA_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_pool_delta_current" / "summary.json"

MIN_SUBSTRATE_SIZE = 18
MAX_SUBSTRATE_SIZE = 24
READY_BARRIER_MIN = 5
BASELINE_SOURCE_ID = "v080_real_frozen_workflow_proximal_substrate"


__all__ = [
    "BASELINE_SOURCE_ID",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_EXPANDED_SUBSTRATE_ADMISSION_OUT_DIR",
    "DEFAULT_EXPANDED_SUBSTRATE_BUILDER_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V091_CLOSEOUT_PATH",
    "DEFAULT_V091_POOL_DELTA_PATH",
    "MAX_SUBSTRATE_SIZE",
    "MIN_SUBSTRATE_SIZE",
    "READY_BARRIER_MIN",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
