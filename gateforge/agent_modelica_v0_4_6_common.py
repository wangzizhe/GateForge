from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_5_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_4_6"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_6_phase_ledger_current"
DEFAULT_STOP_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_6_stop_condition_audit_current"
DEFAULT_DEFERRED_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_6_deferred_question_audit_current"
DEFAULT_V0_5_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_6_v0_5_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_6_closeout_current"

DEFAULT_V040_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_closeout_current" / "summary.json"
DEFAULT_V041_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_closeout_current" / "summary.json"
DEFAULT_V042_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_closeout_current" / "summary.json"
DEFAULT_V043_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_closeout_current" / "summary.json"
DEFAULT_V044_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_closeout_current" / "summary.json"
DEFAULT_V045_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DEFERRED_AUDIT_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_AUDIT_OUT_DIR",
    "DEFAULT_V0_5_HANDOFF_OUT_DIR",
    "DEFAULT_V040_CLOSEOUT_PATH",
    "DEFAULT_V041_CLOSEOUT_PATH",
    "DEFAULT_V042_CLOSEOUT_PATH",
    "DEFAULT_V043_CLOSEOUT_PATH",
    "DEFAULT_V044_CLOSEOUT_PATH",
    "DEFAULT_V045_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
