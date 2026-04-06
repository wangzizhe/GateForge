from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_4_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_5"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_handoff_integrity_current"
DEFAULT_WIDENED_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_widened_manifest_current"
DEFAULT_WIDENED_EXECUTION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_widened_execution_current"
DEFAULT_ADJUDICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_widened_adjudication_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_closeout_current"

DEFAULT_V054_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_4_closeout_current" / "summary.json"

TARGET_ENTRY_PATTERN_ID = "medium_redeclare_alignment.fluid_network_medium_surface_pressure"


__all__ = [
    "DEFAULT_ADJUDICATION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V054_CLOSEOUT_PATH",
    "DEFAULT_WIDENED_EXECUTION_OUT_DIR",
    "DEFAULT_WIDENED_MANIFEST_OUT_DIR",
    "SCHEMA_PREFIX",
    "TARGET_ENTRY_PATTERN_ID",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
