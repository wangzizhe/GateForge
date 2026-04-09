from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_5"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_5_handoff_integrity_current"
DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_5_adjudication_input_table_current"
)
DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_5_expanded_workflow_adjudication_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_5_closeout_current"

DEFAULT_V093_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_closeout_current" / "summary.json"
DEFAULT_V094_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_closeout_current" / "summary.json"
DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_threshold_input_table_current" / "summary.json"
)
DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_expanded_threshold_pack_current" / "summary.json"
)


def dominant_barrier_family(barrier_distribution: dict[str, int]) -> str:
    if not barrier_distribution:
        return "none"
    ordered = sorted(
        ((str(k), int(v)) for k, v in barrier_distribution.items()),
        key=lambda item: (-item[1], item[0]),
    )
    if len(ordered) >= 2 and ordered[0][1] == ordered[1][1]:
        return "mixed_non_success_barriers"
    return ordered[0][0]


__all__ = [
    "DEFAULT_ADJUDICATION_INPUT_TABLE_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_EXPANDED_WORKFLOW_ADJUDICATION_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V093_CLOSEOUT_PATH",
    "DEFAULT_V094_CLOSEOUT_PATH",
    "DEFAULT_V094_EXPANDED_THRESHOLD_PACK_PATH",
    "DEFAULT_V094_THRESHOLD_INPUT_TABLE_PATH",
    "SCHEMA_PREFIX",
    "dominant_barrier_family",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
