from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_5_1_common import load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_5_2"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SIGNAL_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_signal_audit_current"
DEFAULT_ENTRY_TRIAGE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_entry_triage_current"
DEFAULT_ENTRY_SPEC_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_entry_spec_current"
DEFAULT_ADJUDICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_expansion_adjudication_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_2_closeout_current"

DEFAULT_V051_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_5_1_closeout_current" / "summary.json"

MINIMUM_BOUNDED_UNCOVERED_CASE_SHARE_PCT = 15.0
MINIMUM_BOUNDED_UNCOVERED_CASE_COUNT = 4
MINIMUM_SHARED_PATTERN_COUNT = 1


def qualitative_pattern_id(row: dict) -> str:
    bucket = str(row.get("qualitative_bucket") or "").strip()
    family_id = str(row.get("family_id") or "").strip()
    if bucket == "fluid_network_medium_surface_pressure":
        return "medium_redeclare_alignment.fluid_network_medium_surface_pressure"
    if bucket == "medium_cluster_boundary_pressure":
        return "medium_redeclare_alignment.medium_cluster_boundary_pressure"
    if bucket:
        return f"{family_id}.{bucket}" if family_id else bucket
    return family_id or "unknown_pattern"


__all__ = [
    "DEFAULT_ADJUDICATION_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_ENTRY_SPEC_OUT_DIR",
    "DEFAULT_ENTRY_TRIAGE_OUT_DIR",
    "DEFAULT_SIGNAL_AUDIT_OUT_DIR",
    "DEFAULT_V051_CLOSEOUT_PATH",
    "MINIMUM_BOUNDED_UNCOVERED_CASE_COUNT",
    "MINIMUM_BOUNDED_UNCOVERED_CASE_SHARE_PCT",
    "MINIMUM_SHARED_PATTERN_COUNT",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "qualitative_pattern_id",
    "write_json",
    "write_text",
]
