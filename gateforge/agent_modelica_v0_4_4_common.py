from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_3_common import (
    DEFAULT_V042_CLOSEOUT_PATH,
    FAMILY_ORDER,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_4_4"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_authority_slice_freeze_current"
DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_real_authority_recheck_current"
DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_authority_dispatch_audit_current"
DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_promotion_adjudication_current"
DEFAULT_V0_4_5_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_v0_4_5_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_4_closeout_current"

DEFAULT_V043_REAL_SLICE_FREEZE_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_real_slice_freeze_current" / "summary.json"
DEFAULT_V043_REAL_BACKCHECK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_real_backcheck_current" / "summary.json"
DEFAULT_V043_DISPATCH_AUDIT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_dispatch_audit_current" / "summary.json"
DEFAULT_V043_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_3_closeout_current" / "summary.json"


def authority_overlap_case(row: dict) -> bool:
    family_id = str(row.get("family_id") or "")
    complexity = str(row.get("complexity_tier") or "")
    if family_id in {"local_interface_alignment", "medium_redeclare_alignment"}:
        return True
    return complexity == "complex"


def authority_real_candidates(previous_slice: dict) -> list[dict]:
    rows = previous_slice.get("task_rows") if isinstance(previous_slice.get("task_rows"), list) else []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        complexity = str(row.get("complexity_tier") or "")
        if complexity == "simple":
            continue
        candidate = dict(row)
        candidate["authority_overlap_case"] = authority_overlap_case(candidate)
        out.append(candidate)
    return out


def percent(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * float(count) / float(total), 1)


__all__ = [
    "DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR",
    "DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_PROMOTION_ADJUDICATION_OUT_DIR",
    "DEFAULT_REAL_AUTHORITY_RECHECK_OUT_DIR",
    "DEFAULT_V0_4_5_HANDOFF_OUT_DIR",
    "DEFAULT_V042_CLOSEOUT_PATH",
    "DEFAULT_V043_CLOSEOUT_PATH",
    "DEFAULT_V043_DISPATCH_AUDIT_PATH",
    "DEFAULT_V043_REAL_BACKCHECK_PATH",
    "DEFAULT_V043_REAL_SLICE_FREEZE_PATH",
    "FAMILY_ORDER",
    "SCHEMA_PREFIX",
    "authority_overlap_case",
    "authority_real_candidates",
    "load_json",
    "norm",
    "now_utc",
    "percent",
    "write_json",
    "write_text",
]
