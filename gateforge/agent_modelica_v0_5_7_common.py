from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_6_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_7"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_7_phase_ledger_current"
DEFAULT_STOP_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_7_stop_condition_audit_current"
DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_7_boundary_synthesis_current"
DEFAULT_V0_6_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_7_v0_6_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_7_closeout_current"

DEFAULT_V050_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_0_closeout_current" / "summary.json"
DEFAULT_V051_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_closeout_current" / "summary.json"
DEFAULT_V051_CASE_CLASSIFICATION_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_case_classification_current" / "summary.json"
DEFAULT_V051_BOUNDARY_READINESS_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_boundary_readiness_current" / "summary.json"
DEFAULT_V052_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_closeout_current" / "summary.json"
DEFAULT_V053_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_closeout_current" / "summary.json"
DEFAULT_V054_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_4_closeout_current" / "summary.json"
DEFAULT_V055_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_closeout_current" / "summary.json"
DEFAULT_V056_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_6_closeout_current" / "summary.json"


__all__ = [
    "DEFAULT_BOUNDARY_SYNTHESIS_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_AUDIT_OUT_DIR",
    "DEFAULT_V0_6_HANDOFF_OUT_DIR",
    "DEFAULT_V050_CLOSEOUT_PATH",
    "DEFAULT_V051_BOUNDARY_READINESS_PATH",
    "DEFAULT_V051_CASE_CLASSIFICATION_PATH",
    "DEFAULT_V051_CLOSEOUT_PATH",
    "DEFAULT_V052_CLOSEOUT_PATH",
    "DEFAULT_V053_CLOSEOUT_PATH",
    "DEFAULT_V054_CLOSEOUT_PATH",
    "DEFAULT_V055_CLOSEOUT_PATH",
    "DEFAULT_V056_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
