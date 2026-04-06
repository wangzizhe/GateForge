from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_5_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_6"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_6_handoff_integrity_current"
DEFAULT_PROMOTION_CRITERIA_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_6_promotion_criteria_current"
DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_6_promotion_adjudication_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_6_closeout_current"

DEFAULT_V052_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_closeout_current" / "summary.json"
DEFAULT_V052_ENTRY_SPEC_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_entry_spec_current" / "summary.json"
DEFAULT_V053_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_closeout_current" / "summary.json"
DEFAULT_V053_FIRST_FIX_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_first_fix_adjudication_current" / "summary.json"
DEFAULT_V054_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_4_closeout_current" / "summary.json"
DEFAULT_V054_DISCOVERY_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_4_discovery_adjudication_current" / "summary.json"
DEFAULT_V055_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_closeout_current" / "summary.json"
DEFAULT_V055_WIDENED_ADJUDICATION_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_widened_adjudication_current" / "summary.json"
DEFAULT_V055_WIDENED_EXECUTION_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_5_widened_execution_current" / "summary.json"

TARGET_ENTRY_PATTERN_ID = "medium_redeclare_alignment.fluid_network_medium_surface_pressure"
PARENT_FAMILY_ID = "medium_redeclare_alignment"
PARENT_PATCH_TYPES = {
    "insert_redeclare_package_medium",
    "replace_redeclare_clause",
    "replace_medium_package_symbol",
}
BRANCH_PATCH_TYPES = {
    "replace_redeclare_medium_package_path",
    "align_local_medium_redeclare_clause",
}


__all__ = [
    "BRANCH_PATCH_TYPES",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR",
    "DEFAULT_PROMOTION_CRITERIA_OUT_DIR",
    "DEFAULT_V052_CLOSEOUT_PATH",
    "DEFAULT_V052_ENTRY_SPEC_PATH",
    "DEFAULT_V053_CLOSEOUT_PATH",
    "DEFAULT_V053_FIRST_FIX_PATH",
    "DEFAULT_V054_CLOSEOUT_PATH",
    "DEFAULT_V054_DISCOVERY_PATH",
    "DEFAULT_V055_CLOSEOUT_PATH",
    "DEFAULT_V055_WIDENED_ADJUDICATION_PATH",
    "DEFAULT_V055_WIDENED_EXECUTION_PATH",
    "PARENT_FAMILY_ID",
    "PARENT_PATCH_TYPES",
    "SCHEMA_PREFIX",
    "TARGET_ENTRY_PATTERN_ID",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
