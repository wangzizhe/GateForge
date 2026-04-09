from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_9_7"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_7_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_7_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_7_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_7_closeout_current"

DEFAULT_V090_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_0_closeout_current" / "summary.json"
DEFAULT_V091_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_1_closeout_current" / "summary.json"
DEFAULT_V092_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_2_closeout_current" / "summary.json"
DEFAULT_V093_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_3_closeout_current" / "summary.json"
DEFAULT_V094_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_4_closeout_current" / "summary.json"
DEFAULT_V095_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_5_closeout_current" / "summary.json"
DEFAULT_V096_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_9_6_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V090_CLOSEOUT_PATH",
    "DEFAULT_V091_CLOSEOUT_PATH",
    "DEFAULT_V092_CLOSEOUT_PATH",
    "DEFAULT_V093_CLOSEOUT_PATH",
    "DEFAULT_V094_CLOSEOUT_PATH",
    "DEFAULT_V095_CLOSEOUT_PATH",
    "DEFAULT_V096_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
