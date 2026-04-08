from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_5"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_5_handoff_integrity_current"
)
DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_5_remaining_gap_characterization_current"
)
DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_5_refinement_worth_it_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_5_closeout_current"

DEFAULT_V081_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_closeout_current" / "summary.json"
)
DEFAULT_V082_THRESHOLD_FREEZE_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_threshold_freeze_current" / "summary.json"
)
DEFAULT_V084_CLOSEOUT_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_8_4_closeout_current" / "summary.json"
)


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REFINEMENT_WORTH_IT_SUMMARY_OUT_DIR",
    "DEFAULT_REMAINING_GAP_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_V081_CLOSEOUT_PATH",
    "DEFAULT_V082_THRESHOLD_FREEZE_PATH",
    "DEFAULT_V084_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
