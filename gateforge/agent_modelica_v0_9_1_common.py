from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_1"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_handoff_integrity_current"
DEFAULT_SOURCE_ADMISSION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_source_admission_current"
DEFAULT_POOL_DELTA_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_pool_delta_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_closeout_current"

DEFAULT_V090_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_closeout_current" / "summary.json"
DEFAULT_V090_GOVERNANCE_PACK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_governance_pack_current" / "summary.json"

DEFAULT_UPLIFT_TASKSET_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_l4_uplift_evidence_v0" / "challenge" / "taskset_frozen.json"
)
DEFAULT_HOLDOUT_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_layer4_holdout_v0_3_1" / "taskset_frozen.json"
DEFAULT_HOLDOUT_SUMMARY_PATH = REPO_ROOT / "artifacts" / "agent_modelica_layer4_holdout_v0_3_1" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_HOLDOUT_SUMMARY_PATH",
    "DEFAULT_HOLDOUT_TASKSET_PATH",
    "DEFAULT_POOL_DELTA_OUT_DIR",
    "DEFAULT_SOURCE_ADMISSION_OUT_DIR",
    "DEFAULT_UPLIFT_TASKSET_PATH",
    "DEFAULT_V090_CLOSEOUT_PATH",
    "DEFAULT_V090_GOVERNANCE_PACK_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
