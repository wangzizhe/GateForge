from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_11_7"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_7_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_7_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_7_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_7_closeout_current"

DEFAULT_V110_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_0_closeout_current" / "summary.json"
DEFAULT_V111_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_closeout_current" / "summary.json"
DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V113_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_3_closeout_current" / "summary.json"
DEFAULT_V114_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_4_closeout_current" / "summary.json"
DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"
DEFAULT_V116_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_6_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V110_CLOSEOUT_PATH",
    "DEFAULT_V111_CLOSEOUT_PATH",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V113_CLOSEOUT_PATH",
    "DEFAULT_V114_CLOSEOUT_PATH",
    "DEFAULT_V115_CLOSEOUT_PATH",
    "DEFAULT_V116_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
