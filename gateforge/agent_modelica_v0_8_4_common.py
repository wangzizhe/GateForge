from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_4"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_4_handoff_integrity_current"
)
DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_4_frozen_baseline_adjudication_current"
)
DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_4_route_interpretation_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_4_closeout_current"

DEFAULT_V081_CHARACTERIZATION_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_workflow_profile_characterization_current" / "summary.json"
)
DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_threshold_input_table_current" / "summary.json"
)
DEFAULT_V082_THRESHOLD_FREEZE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_threshold_freeze_current" / "summary.json"
)
DEFAULT_V083_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_3_closeout_current" / "summary.json"
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
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_FROZEN_BASELINE_ADJUDICATION_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_ROUTE_INTERPRETATION_SUMMARY_OUT_DIR",
    "DEFAULT_V081_CHARACTERIZATION_PATH",
    "DEFAULT_V082_THRESHOLD_FREEZE_PATH",
    "DEFAULT_V082_THRESHOLD_INPUT_TABLE_PATH",
    "DEFAULT_V083_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "dominant_barrier_family",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
