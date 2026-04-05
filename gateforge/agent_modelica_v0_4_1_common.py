from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_0_common import (
    DEFAULT_BENCHMARK_FREEZE_OUT_DIR as DEFAULT_V040_BENCHMARK_OUT_DIR,
    DEFAULT_CONDITIONING_AUDIT_OUT_DIR as DEFAULT_V040_AUDIT_OUT_DIR,
    DEFAULT_EXPERIENCE_STORE_PATH,
    SCHEMA_PREFIX as V040_SCHEMA_PREFIX,
    STAGE2_DOMINANT_STAGE_SUBTYPE,
    STAGE2_ERROR_SUBTYPE,
    STAGE2_FAILURE_TYPE,
    STAGE2_RESIDUAL_SIGNAL_CLUSTER,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_4_1"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_signal_source_audit_current"
DEFAULT_SIGNAL_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_signal_pack_current"
DEFAULT_REAUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_conditioning_reaudit_current"
DEFAULT_GAIN_UNLOCK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_gain_unlock_gate_current"
DEFAULT_V0_4_2_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_v0_4_2_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_1_closeout_current"

DEFAULT_V040_BENCHMARK_PATH = DEFAULT_V040_BENCHMARK_OUT_DIR / "benchmark_pack.json"
DEFAULT_V040_AUDIT_PATH = DEFAULT_V040_AUDIT_OUT_DIR / "summary.json"
DEFAULT_V040_HANDOFF_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_v0_4_1_handoff_current" / "summary.json"

MIN_EXACT_SIGNALS_PER_FAMILY = 3


def benchmark_tasks(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def family_counts(rows: list[dict], key: str = "family_id") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def signal_rule_id(family_id: str, patch_type: str) -> str:
    family = norm(family_id)
    patch = norm(patch_type) or "unknown_patch"
    return f"rule_{family}_{patch}"


def signal_action_key(family_id: str, patch_type: str) -> str:
    family = norm(family_id)
    patch = norm(patch_type) or "unknown_patch"
    return f"repair|{family}|{patch}|stage2_signal_pack_v0_4_1"


def signal_action_type(family_id: str, patch_type: str) -> str:
    family = norm(family_id)
    patch = norm(patch_type) or "unknown_patch"
    return f"{family}:{patch}"


def family_ready(counts: dict[str, int]) -> bool:
    return all(int(counts.get(family_id) or 0) >= MIN_EXACT_SIGNALS_PER_FAMILY for family_id in (
        "component_api_alignment",
        "local_interface_alignment",
        "medium_redeclare_alignment",
    ))


__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_EXPERIENCE_STORE_PATH",
    "DEFAULT_GAIN_UNLOCK_OUT_DIR",
    "DEFAULT_REAUDIT_OUT_DIR",
    "DEFAULT_SIGNAL_PACK_OUT_DIR",
    "DEFAULT_SIGNAL_SOURCE_AUDIT_OUT_DIR",
    "DEFAULT_V0_4_2_HANDOFF_OUT_DIR",
    "DEFAULT_V040_AUDIT_PATH",
    "DEFAULT_V040_BENCHMARK_PATH",
    "DEFAULT_V040_HANDOFF_PATH",
    "MIN_EXACT_SIGNALS_PER_FAMILY",
    "SCHEMA_PREFIX",
    "STAGE2_DOMINANT_STAGE_SUBTYPE",
    "STAGE2_ERROR_SUBTYPE",
    "STAGE2_FAILURE_TYPE",
    "STAGE2_RESIDUAL_SIGNAL_CLUSTER",
    "V040_SCHEMA_PREFIX",
    "benchmark_tasks",
    "family_counts",
    "family_ready",
    "load_json",
    "norm",
    "now_utc",
    "signal_action_key",
    "signal_action_type",
    "signal_rule_id",
    "write_json",
    "write_text",
]
