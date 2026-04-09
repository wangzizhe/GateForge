from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_6"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_6_handoff_integrity_current"
DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_6_remaining_uncertainty_characterization_current"
)
DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_9_6_expansion_worth_it_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_6_closeout_current"

DEFAULT_V091_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_closeout_current" / "summary.json"
DEFAULT_V092_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_closeout_current" / "summary.json"
DEFAULT_V093_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_closeout_current" / "summary.json"
DEFAULT_V094_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_closeout_current" / "summary.json"
DEFAULT_V095_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_5_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_EXPANSION_WORTH_IT_SUMMARY_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_V091_CLOSEOUT_PATH",
    "DEFAULT_V092_CLOSEOUT_PATH",
    "DEFAULT_V093_CLOSEOUT_PATH",
    "DEFAULT_V094_CLOSEOUT_PATH",
    "DEFAULT_V095_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
