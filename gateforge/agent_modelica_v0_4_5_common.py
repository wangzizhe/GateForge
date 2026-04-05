from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_4_common import (
    DEFAULT_V043_CLOSEOUT_PATH,
    FAMILY_ORDER,
    load_json,
    norm,
    now_utc,
    percent,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_4_5"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SLICE_LOCK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_policy_slice_lock_current"
DEFAULT_POLICY_COMPARISON_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_policy_comparison_current"
DEFAULT_POLICY_CLEANLINESS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_policy_cleanliness_current"
DEFAULT_ADJUDICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_policy_adjudication_current"
DEFAULT_V0_4_6_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_v0_4_6_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_5_closeout_current"

DEFAULT_V044_AUTHORITY_SLICE_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_authority_slice_freeze_current" / "summary.json"
DEFAULT_V044_REAL_RECHECK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_real_authority_recheck_current" / "summary.json"
DEFAULT_V044_DISPATCH_AUDIT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_authority_dispatch_audit_current" / "summary.json"
DEFAULT_V044_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_closeout_current" / "summary.json"


BASELINE_POLICY_ID = "stage_gated_with_arbitration"
ALTERNATIVE_POLICY_ID = "medium_first_for_overlap_then_baseline_fallback"


def baseline_policy_name() -> str:
    return BASELINE_POLICY_ID


def alternative_policy_name() -> str:
    return ALTERNATIVE_POLICY_ID


__all__ = [
    "ALTERNATIVE_POLICY_ID",
    "BASELINE_POLICY_ID",
    "DEFAULT_ADJUDICATION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_POLICY_CLEANLINESS_OUT_DIR",
    "DEFAULT_POLICY_COMPARISON_OUT_DIR",
    "DEFAULT_SLICE_LOCK_OUT_DIR",
    "DEFAULT_V0_4_6_HANDOFF_OUT_DIR",
    "DEFAULT_V043_CLOSEOUT_PATH",
    "DEFAULT_V044_AUTHORITY_SLICE_PATH",
    "DEFAULT_V044_CLOSEOUT_PATH",
    "DEFAULT_V044_DISPATCH_AUDIT_PATH",
    "DEFAULT_V044_REAL_RECHECK_PATH",
    "FAMILY_ORDER",
    "SCHEMA_PREFIX",
    "alternative_policy_name",
    "baseline_policy_name",
    "load_json",
    "norm",
    "now_utc",
    "percent",
    "write_json",
    "write_text",
]
