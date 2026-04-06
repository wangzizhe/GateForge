from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_2_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_3"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_handoff_integrity_current"
DEFAULT_ENTRY_TASKSET_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_entry_taskset_current"
DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_first_fix_evidence_current"
DEFAULT_ADJUDICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_first_fix_adjudication_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_3_closeout_current"

DEFAULT_V052_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_closeout_current" / "summary.json"
DEFAULT_V051_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_closeout_current" / "summary.json"

TARGET_ENTRY_PATTERN_ID = "medium_redeclare_alignment.fluid_network_medium_surface_pressure"
TARGET_FIRST_FAILURE_BUCKET = "stage_2_structural_balance_reference|undefined_symbol"
ALLOWED_PATCH_TYPES = [
    "replace_redeclare_medium_package_path",
    "align_local_medium_redeclare_clause",
]


__all__ = [
    "ALLOWED_PATCH_TYPES",
    "DEFAULT_ADJUDICATION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_ENTRY_TASKSET_OUT_DIR",
    "DEFAULT_FIRST_FIX_EVIDENCE_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V051_CLOSEOUT_PATH",
    "DEFAULT_V052_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "TARGET_ENTRY_PATTERN_ID",
    "TARGET_FIRST_FAILURE_BUCKET",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
