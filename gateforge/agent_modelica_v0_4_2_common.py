from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_4_1_common import (
    DEFAULT_SIGNAL_PACK_OUT_DIR as DEFAULT_V041_SIGNAL_PACK_OUT_DIR,
    DEFAULT_V0_4_2_HANDOFF_OUT_DIR as DEFAULT_V041_HANDOFF_OUT_DIR,
    STAGE2_DOMINANT_STAGE_SUBTYPE,
    STAGE2_ERROR_SUBTYPE,
    STAGE2_FAILURE_TYPE,
    STAGE2_RESIDUAL_SIGNAL_CLUSTER,
    benchmark_tasks,
    family_counts,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_4_2"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BENCHMARK_LOCK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_benchmark_lock_current"
DEFAULT_SYNTHETIC_GAIN_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_synthetic_gain_current"
DEFAULT_DISPATCH_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_dispatch_audit_current"
DEFAULT_REAL_BACKCHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_real_backcheck_current"
DEFAULT_V0_4_3_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_v0_4_3_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_2_closeout_current"

DEFAULT_V040_BENCHMARK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_benchmark_freeze_current" / "benchmark_pack.json"
DEFAULT_V041_SIGNAL_PACK_PATH = DEFAULT_V041_SIGNAL_PACK_OUT_DIR / "signal_pack.json"
DEFAULT_V041_HANDOFF_PATH = DEFAULT_V041_HANDOFF_OUT_DIR / "summary.json"
DEFAULT_V0317_GENERATION_CENSUS_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "summary.json"
DEFAULT_V0318_DIAGNOSIS_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_18_stage2_diagnosis_current" / "records.json"

FAMILY_ORDER = [
    "component_api_alignment",
    "local_interface_alignment",
    "medium_redeclare_alignment",
]

REAL_BACKCHECK_SUPPORTED_ACTION_TYPES = {
    "component_api_alignment": "component_api_alignment",
    "medium_redeclare_alignment": "medium_redeclare_alignment",
}


def benchmark_task_rows(payload: dict) -> list[dict]:
    return benchmark_tasks(payload)


def family_grouped_tasks(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        family_id = norm(row.get("family_id"))
        if not family_id:
            continue
        grouped.setdefault(family_id, []).append(dict(row))
    for family_id in grouped:
        grouped[family_id] = sorted(
            grouped[family_id],
            key=lambda item: (
                norm(item.get("task_role")),
                norm(item.get("complexity_tier")),
                norm(item.get("benchmark_task_id")),
            ),
        )
    return grouped


def policy_baseline() -> dict:
    return {
        "policy_mechanism": "stage-gated_with_arbitration",
        "dispatch_priority": list(FAMILY_ORDER),
        "policy_basis": "narrowest_patch_scope_first",
        "escalation_rule": "advance_to_next_family_only_if_no_signature_advance",
    }


def real_family_from_action_type(action_type: str) -> str:
    return REAL_BACKCHECK_SUPPORTED_ACTION_TYPES.get(norm(action_type), "")


def real_backcheck_candidate_records(payload: dict) -> list[dict]:
    rows = payload.get("records")
    if not isinstance(rows, list):
        return []
    selected: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        family_id = real_family_from_action_type(str(row.get("proposed_action_type") or ""))
        if not family_id:
            continue
        first_failure = row.get("first_failure") if isinstance(row.get("first_failure"), dict) else {}
        if norm(first_failure.get("dominant_stage_subtype")) != STAGE2_DOMINANT_STAGE_SUBTYPE:
            continue
        selected.append(dict(row, family_id=family_id))
    return selected


def signal_rows(payload: dict) -> list[dict]:
    rows = payload.get("signal_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


__all__ = [
    "DEFAULT_BENCHMARK_LOCK_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DISPATCH_AUDIT_OUT_DIR",
    "DEFAULT_REAL_BACKCHECK_OUT_DIR",
    "DEFAULT_SYNTHETIC_GAIN_OUT_DIR",
    "DEFAULT_V0_4_3_HANDOFF_OUT_DIR",
    "DEFAULT_V0317_GENERATION_CENSUS_PATH",
    "DEFAULT_V0318_DIAGNOSIS_PATH",
    "DEFAULT_V040_BENCHMARK_PATH",
    "DEFAULT_V041_HANDOFF_PATH",
    "DEFAULT_V041_SIGNAL_PACK_PATH",
    "FAMILY_ORDER",
    "SCHEMA_PREFIX",
    "STAGE2_DOMINANT_STAGE_SUBTYPE",
    "STAGE2_ERROR_SUBTYPE",
    "STAGE2_FAILURE_TYPE",
    "STAGE2_RESIDUAL_SIGNAL_CLUSTER",
    "benchmark_task_rows",
    "family_counts",
    "family_grouped_tasks",
    "load_json",
    "norm",
    "now_utc",
    "policy_baseline",
    "real_backcheck_candidate_records",
    "real_family_from_action_type",
    "signal_rows",
    "write_json",
    "write_text",
]
