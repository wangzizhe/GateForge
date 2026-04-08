from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_8_6"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_6_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_6_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_6_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_6_closeout_current"

DEFAULT_V080_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_0_closeout_current" / "summary.json"
DEFAULT_V081_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_1_closeout_current" / "summary.json"
DEFAULT_V082_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_2_closeout_current" / "summary.json"
DEFAULT_V083_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_3_closeout_current" / "summary.json"
DEFAULT_V084_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_4_closeout_current" / "summary.json"
DEFAULT_V085_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_8_5_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V080_CLOSEOUT_PATH",
    "DEFAULT_V081_CLOSEOUT_PATH",
    "DEFAULT_V082_CLOSEOUT_PATH",
    "DEFAULT_V083_CLOSEOUT_PATH",
    "DEFAULT_V084_CLOSEOUT_PATH",
    "DEFAULT_V085_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
