from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_8"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_8_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_8_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_8_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_8_closeout_current"

DEFAULT_V100_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_0_closeout_current" / "summary.json"
DEFAULT_V101_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_1_closeout_current" / "summary.json"
DEFAULT_V102_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_2_closeout_current" / "summary.json"
DEFAULT_V103_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_closeout_current" / "summary.json"
DEFAULT_V104_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_closeout_current" / "summary.json"
DEFAULT_V105_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_5_closeout_current" / "summary.json"
DEFAULT_V106_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_closeout_current" / "summary.json"
DEFAULT_V107_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_7_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V100_CLOSEOUT_PATH",
    "DEFAULT_V101_CLOSEOUT_PATH",
    "DEFAULT_V102_CLOSEOUT_PATH",
    "DEFAULT_V103_CLOSEOUT_PATH",
    "DEFAULT_V104_CLOSEOUT_PATH",
    "DEFAULT_V105_CLOSEOUT_PATH",
    "DEFAULT_V106_CLOSEOUT_PATH",
    "DEFAULT_V107_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
