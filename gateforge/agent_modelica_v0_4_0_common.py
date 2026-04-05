from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc


SCHEMA_PREFIX = "agent_modelica_v0_4_0"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONDITIONING_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_conditioning_reactivation_audit_current"
DEFAULT_BENCHMARK_FREEZE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_benchmark_freeze_current"
DEFAULT_SYNTHETIC_BASELINE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_synthetic_baseline_current"
DEFAULT_V0_4_1_HANDOFF_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_v0_4_1_handoff_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_4_0_closeout_current"

DEFAULT_V0334_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_closeout_current" / "summary.json"
DEFAULT_V0334_HANDOFF_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_34_v0_4_handoff_current" / "summary.json"
DEFAULT_EXPERIENCE_STORE_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"

DEFAULT_V0322_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_surface_export_audit_current" / "active_taskset.json"
DEFAULT_V0328_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_28_surface_export_audit_current" / "active_taskset.json"
DEFAULT_V0333_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_surface_export_audit_current" / "active_taskset.json"

STAGE2_FAILURE_TYPE = "model_check_error"
STAGE2_ERROR_SUBTYPE = "undefined_symbol"
STAGE2_DOMINANT_STAGE_SUBTYPE = "stage_2_structural_balance_reference"
STAGE2_RESIDUAL_SIGNAL_CLUSTER = "stage_2_structural_balance_reference|undefined_symbol"

DEFAULT_SINGLE_TASKS_PER_FAMILY = 10
DEFAULT_DUAL_TASKS_PER_FAMILY = 6

FAMILY_SOURCES = [
    {
        "family_id": "component_api_alignment",
        "taskset_path": DEFAULT_V0322_TASKSET_PATH,
        "single_key": "single_tasks",
        "dual_key": "dual_sidecar_tasks",
        "source_closeout_path": REPO_ROOT / "artifacts" / "agent_modelica_v0_3_22_closeout_current" / "summary.json",
    },
    {
        "family_id": "local_interface_alignment",
        "taskset_path": DEFAULT_V0328_TASKSET_PATH,
        "single_key": "single_tasks",
        "dual_key": "dual_sidecar_tasks",
        "source_closeout_path": REPO_ROOT / "artifacts" / "agent_modelica_v0_3_28_closeout_current" / "summary.json",
    },
    {
        "family_id": "medium_redeclare_alignment",
        "taskset_path": DEFAULT_V0333_TASKSET_PATH,
        "single_key": "single_tasks",
        "dual_key": "dual_tasks",
        "source_closeout_path": REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_closeout_current" / "summary.json",
    },
]


def task_rows(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def deterministic_pick(rows: list[dict], limit: int) -> list[dict]:
    if limit <= 0:
        return []
    ordered = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: (
            norm(row.get("complexity_tier")),
            norm(row.get("task_id")),
        ),
    )
    return [dict(row) for row in ordered[:limit]]


def allowed_patch_types_for_row(row: dict) -> list[str]:
    raw = row.get("allowed_patch_types")
    if isinstance(raw, list):
        values = [norm(item) for item in raw if norm(item)]
        if values:
            return values
    repair_steps = row.get("repair_steps")
    if isinstance(repair_steps, list):
        values = [norm(step.get("patch_type")) for step in repair_steps if isinstance(step, dict) and norm(step.get("patch_type"))]
        if values:
            return values
    patch_type = norm(row.get("patch_type"))
    return [patch_type] if patch_type else []


def first_patch_type(row: dict) -> str:
    patch_type = norm(row.get("patch_type"))
    if patch_type:
        return patch_type
    repair_steps = row.get("repair_steps")
    if isinstance(repair_steps, list):
        for step in repair_steps:
            if isinstance(step, dict) and norm(step.get("patch_type")):
                return norm(step.get("patch_type"))
    return ""


def family_dispatch_policy() -> dict:
    return {
        "policy_mechanism": "stage-gated_with_arbitration",
        "dispatch_priority": [
            "component_api_alignment",
            "local_interface_alignment",
            "medium_redeclare_alignment",
        ],
        "policy_basis": "narrowest_patch_scope_first",
    }


def benchmark_task_payload(
    *,
    family_id: str,
    family_order: int,
    task_role: str,
    row: dict,
    source_taskset_path: str,
) -> dict:
    payload = {
        "benchmark_task_id": f"{family_id}|{task_role}|{norm(row.get('task_id'))}",
        "family_id": family_id,
        "family_order": family_order,
        "task_role": task_role,
        "source_task_id": norm(row.get("task_id")),
        "source_taskset_path": str(Path(source_taskset_path).resolve()),
        "complexity_tier": norm(row.get("complexity_tier")),
        "patch_type": first_patch_type(row),
        "allowed_patch_types": allowed_patch_types_for_row(row),
        "declared_failure_type": norm(row.get("declared_failure_type")) or STAGE2_FAILURE_TYPE,
        "error_subtype": STAGE2_ERROR_SUBTYPE,
        "dominant_stage_subtype": STAGE2_DOMINANT_STAGE_SUBTYPE,
        "residual_signal_cluster": STAGE2_RESIDUAL_SIGNAL_CLUSTER,
        "family_target_bucket": STAGE2_RESIDUAL_SIGNAL_CLUSTER,
        "routing_policy": "family_specific_bounded_patch_contract",
        "conditioning_metadata_ready": True,
    }
    for key in (
        "component_family",
        "component_type",
        "component_name",
        "component_subtype",
        "pipe_slice_context",
        "candidate_key",
        "wrong_symbol",
        "correct_symbol",
        "correct_target",
        "pattern_id",
        "variant_tag",
        "model_name",
        "source_id",
    ):
        value = row.get(key)
        if value is not None:
            payload[key] = value
    return payload


__all__ = [
    "DEFAULT_BENCHMARK_FREEZE_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_CONDITIONING_AUDIT_OUT_DIR",
    "DEFAULT_DUAL_TASKS_PER_FAMILY",
    "DEFAULT_EXPERIENCE_STORE_PATH",
    "DEFAULT_SINGLE_TASKS_PER_FAMILY",
    "DEFAULT_SYNTHETIC_BASELINE_OUT_DIR",
    "DEFAULT_V0_4_1_HANDOFF_OUT_DIR",
    "DEFAULT_V0322_TASKSET_PATH",
    "DEFAULT_V0328_TASKSET_PATH",
    "DEFAULT_V0333_TASKSET_PATH",
    "DEFAULT_V0334_CLOSEOUT_PATH",
    "DEFAULT_V0334_HANDOFF_PATH",
    "FAMILY_SOURCES",
    "SCHEMA_PREFIX",
    "STAGE2_DOMINANT_STAGE_SUBTYPE",
    "STAGE2_ERROR_SUBTYPE",
    "STAGE2_FAILURE_TYPE",
    "STAGE2_RESIDUAL_SIGNAL_CLUSTER",
    "allowed_patch_types_for_row",
    "benchmark_task_payload",
    "deterministic_pick",
    "family_dispatch_policy",
    "first_patch_type",
    "load_json",
    "norm",
    "now_utc",
    "task_rows",
    "write_json",
    "write_text",
]
