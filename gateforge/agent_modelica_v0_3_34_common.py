from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc


SCHEMA_PREFIX = "agent_modelica_v0_3_34"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FAMILY_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_family_ledger_current"
DEFAULT_STOP_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_stop_condition_audit_current"
DEFAULT_REAL_DIST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_real_distribution_synthesis_current"
DEFAULT_V0_4_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_v0_4_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_closeout_current"

DEFAULT_V0317_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_closeout_current" / "summary.json"
DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_distribution_analysis_current" / "summary.json"
DEFAULT_V0317_GENERATION_CENSUS_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "summary.json"
DEFAULT_V0317_ONE_STEP_REPAIR_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_one_step_live_repair_current" / "summary.json"
DEFAULT_V0322_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_closeout_current" / "summary.json"
DEFAULT_V0328_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_28_closeout_current" / "summary.json"
DEFAULT_V0331_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_closeout_current" / "summary.json"
DEFAULT_V0333_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_closeout_current" / "summary.json"


def conclusion_of(payload: dict) -> dict:
    value = payload.get("conclusion")
    return value if isinstance(value, dict) else {}


def tier_stage_count(tier_summary: dict, stage_prefix: str) -> int:
    total = 0
    for tier in ("simple", "medium", "complex"):
        row = (tier_summary.get(tier) or {}) if isinstance(tier_summary, dict) else {}
        dist = row.get("first_failure_stage_distribution") if isinstance(row.get("first_failure_stage_distribution"), dict) else {}
        for stage_name, count in dist.items():
            if norm(stage_name).startswith(norm(stage_prefix)):
                total += int(count or 0)
    return total


def second_residual_stage_count(distribution: dict, stage_prefix: str) -> int:
    total = 0
    for stage_name, count in (distribution or {}).items():
        if norm(stage_name).startswith(norm(stage_prefix)):
            total += int(count or 0)
    return total


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_FAMILY_LEDGER_OUT_DIR",
    "DEFAULT_REAL_DIST_OUT_DIR",
    "DEFAULT_STOP_AUDIT_OUT_DIR",
    "DEFAULT_V0_4_HANDOFF_OUT_DIR",
    "DEFAULT_V0317_CLOSEOUT_PATH",
    "DEFAULT_V0317_DISTRIBUTION_ANALYSIS_PATH",
    "DEFAULT_V0317_GENERATION_CENSUS_PATH",
    "DEFAULT_V0317_ONE_STEP_REPAIR_PATH",
    "DEFAULT_V0322_CLOSEOUT_PATH",
    "DEFAULT_V0328_CLOSEOUT_PATH",
    "DEFAULT_V0331_CLOSEOUT_PATH",
    "DEFAULT_V0333_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "conclusion_of",
    "load_json",
    "norm",
    "now_utc",
    "second_residual_stage_count",
    "tier_stage_count",
    "write_json",
    "write_text",
]
