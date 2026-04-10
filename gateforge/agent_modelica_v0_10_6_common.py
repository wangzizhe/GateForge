from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_6"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_handoff_integrity_current"
DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_real_origin_adjudication_input_table_current"
)
DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_first_real_origin_workflow_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_closeout_current"

DEFAULT_V104_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_closeout_current" / "summary.json"
DEFAULT_V105_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_closeout_current" / "summary.json"
DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_real_origin_threshold_input_table_current" / "summary.json"
)
DEFAULT_V105_THRESHOLD_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_first_real_origin_threshold_pack_current" / "summary.json"
)

EXPECTED_EXECUTION_SOURCE = "frozen_real_origin_substrate_deterministic_replay"


def dominant_non_success_family(label_distribution: dict[str, int]) -> str:
    cleaned = {str(k): int(v) for k, v in (label_distribution or {}).items() if str(k).strip()}
    if not cleaned:
        return "none"
    return sorted(cleaned.items(), key=lambda item: (-item[1], item[0]))[0][0]


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_FIRST_REAL_ORIGIN_WORKFLOW_ADJUDICATION_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REAL_ORIGIN_ADJUDICATION_INPUT_TABLE_OUT_DIR",
    "DEFAULT_V104_CLOSEOUT_PATH",
    "DEFAULT_V105_CLOSEOUT_PATH",
    "DEFAULT_V105_THRESHOLD_INPUT_TABLE_PATH",
    "DEFAULT_V105_THRESHOLD_PACK_PATH",
    "EXPECTED_EXECUTION_SOURCE",
    "SCHEMA_PREFIX",
    "dominant_non_success_family",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
