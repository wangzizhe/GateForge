from __future__ import annotations

from pathlib import Path

from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc
from .agent_modelica_v0_3_29_common import apply_repair_step, build_mutated_text
from .agent_modelica_v0_3_30_common import (
    apply_medium_redeclare_discovery_patch,
    build_medium_candidate_rhs_symbols,
    medium_redeclare_target_hit,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
)
from .agent_modelica_v0_3_32_common import (
    ALLOWED_PATCH_TYPES,
    anti_noop_rejected,
    apply_pipe_slice_discovery_patch,
    build_pipe_dual_spec,
    build_pipe_single_spec,
    pipe_slice_target_hit,
    probe_resolved_result,
    probe_target_result,
    source_row_for,
)


SCHEMA_PREFIX = "agent_modelica_v0_3_33"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_coverage_manifest_current"
DEFAULT_SURFACE_AUDIT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_surface_export_audit_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_first_fix_evidence_current"
DEFAULT_DUAL_RECHECK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_dual_recheck_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_33_closeout_current"

DEFAULT_V0331_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_closeout_current" / "summary.json"
DEFAULT_V0332_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_32_closeout_current" / "summary.json"

PIPE_SINGLE_VARIANTS = {
    "pipe": [
        ("canonical_alias", "MediumPipe"),
        ("neighbor_alias", "MediumPipeAlt"),
        ("cluster_alias", "MediumPipeNode"),
    ],
    "port_a": [
        ("canonical_alias", "MediumPort"),
        ("neighbor_alias", "MediumPortAlt"),
        ("cluster_alias", "MediumPortNode"),
    ],
    "port_b": [
        ("canonical_alias", "MediumPort"),
        ("neighbor_alias", "MediumPortAlt"),
        ("cluster_alias", "MediumPortNode"),
    ],
}

PIPE_SINGLE_BLUEPRINTS = [
    ("medium_port_pipe_tank", "pipe"),
    ("medium_port_pipe_tank", "port_a"),
    ("medium_port_pipe_tank", "port_b"),
    ("medium_port_pipe_volume", "pipe"),
    ("medium_port_pipe_volume", "port_a"),
    ("medium_port_pipe_volume", "port_b"),
    ("medium_boundary_pipe_volume_sink", "pipe"),
    ("medium_boundary_pipe_tank_sink", "pipe"),
    ("medium_source_pipe_tank_ports", "pipe"),
    ("medium_source_pipe_tank_ports", "port_a"),
    ("medium_source_pipe_tank_ports", "port_b"),
]

PIPE_DUAL_BLUEPRINTS = [
    ("medium_port_pipe_tank", "pipe", "port_a", "pipe_component_like"),
    ("medium_port_pipe_tank", "pipe", "port_b", "pipe_component_like"),
    ("medium_port_pipe_tank", "port_a", "port_b", "fluid_port_like"),
    ("medium_port_pipe_tank", "port_b", "port_a", "fluid_port_like"),
    ("medium_port_pipe_tank", "port_a", "pipe", "mixed_pipe_port_like"),
    ("medium_port_pipe_volume", "pipe", "port_a", "pipe_component_like"),
    ("medium_port_pipe_volume", "pipe", "port_b", "pipe_component_like"),
    ("medium_port_pipe_volume", "port_a", "port_b", "fluid_port_like"),
    ("medium_port_pipe_volume", "port_b", "port_a", "fluid_port_like"),
    ("medium_port_pipe_volume", "port_a", "pipe", "mixed_pipe_port_like"),
    ("medium_source_pipe_tank_ports", "pipe", "port_a", "pipe_component_like"),
    ("medium_source_pipe_tank_ports", "pipe", "port_b", "pipe_component_like"),
    ("medium_source_pipe_tank_ports", "port_a", "port_b", "fluid_port_like"),
    ("medium_source_pipe_tank_ports", "port_b", "port_a", "fluid_port_like"),
    ("medium_source_pipe_tank_ports", "port_a", "pipe", "mixed_pipe_port_like"),
]


def handoff_substrate_valid(v0331_closeout: dict, v0332_closeout: dict) -> bool:
    v0331_decision = norm(((v0331_closeout.get("conclusion") or {}).get("version_decision")))
    v0331_confidence = norm(((v0331_closeout.get("conclusion") or {}).get("authority_confidence")))
    v0332_decision = norm(((v0332_closeout.get("conclusion") or {}).get("version_decision")))
    return (
        v0331_decision in {
            "stage2_medium_redeclare_discovery_coverage_partially_ready",
            "stage2_medium_redeclare_discovery_coverage_ready",
        }
        and v0331_confidence == "supported"
        and v0332_decision == "stage2_medium_redeclare_pipe_slice_discovery_ready"
    )


def _replace_wrong_symbol(spec: dict, wrong_symbol: str, variant_tag: str) -> dict:
    row = dict(spec)
    original = norm(spec.get("wrong_symbol"))
    row["wrong_symbol"] = norm(wrong_symbol)
    row["task_id"] = f"{norm(spec.get('task_id'))}__{norm(variant_tag)}"
    replacements = []
    for left, right in list(spec.get("injection_replacements") or []):
        replacements.append((norm(left), norm(right).replace(original, norm(wrong_symbol), 1)))
    row["injection_replacements"] = replacements
    new_steps = []
    for step in list(spec.get("repair_steps") or []):
        new_step = dict(step)
        new_step["match_text"] = norm(step.get("match_text")).replace(original, norm(wrong_symbol), 1)
        new_steps.append(new_step)
    row["repair_steps"] = new_steps
    row["variant_tag"] = norm(variant_tag)
    return row


def build_v0333_single_specs() -> list[dict]:
    rows: list[dict] = []
    for source_id, component_name in PIPE_SINGLE_BLUEPRINTS:
        base = build_pipe_single_spec(source_id, component_name)
        for variant_tag, wrong_symbol in PIPE_SINGLE_VARIANTS.get(norm(component_name), []):
            row = _replace_wrong_symbol(base, wrong_symbol, variant_tag)
            row["pipe_slice_context"] = "pipe_component_like" if norm(component_name) == "pipe" else "fluid_port_like"
            rows.append(row)
    return rows


def build_v0333_dual_specs() -> list[dict]:
    rows: list[dict] = []
    for source_id, first_component, second_component, context in PIPE_DUAL_BLUEPRINTS:
        row = build_pipe_dual_spec(source_id, first_component, second_component)
        row["pipe_slice_context"] = norm(context)
        rows.append(row)
    return rows


def coverage_target_hit(result: dict) -> bool:
    return pipe_slice_target_hit(result) or medium_redeclare_target_hit(result)


def first_fix_subtype_metrics(rows: list[dict], context: str) -> dict:
    selected = [row for row in rows if norm(row.get("pipe_slice_context")) == norm(context)]
    count = len(selected)
    if not count:
        return {"task_count": 0}
    return {
        "task_count": count,
        "candidate_contains_canonical_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("candidate_contains_canonical"))) / float(count), 1),
        "candidate_top1_canonical_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("candidate_top1_is_canonical"))) / float(count), 1),
        "patch_applied_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("patch_applied"))) / float(count), 1),
        "signature_advance_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("signature_advance"))) / float(count), 1),
        "drift_to_compile_failure_unknown_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("drift_to_compile_failure_unknown"))) / float(count), 1),
    }


def dual_context_metrics(rows: list[dict], context: str) -> dict:
    selected = [row for row in rows if norm(row.get("pipe_slice_context")) == norm(context)]
    count = len(selected)
    if not count:
        return {"task_count": 0}
    return {
        "task_count": count,
        "pipe_slice_second_residual_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("pipe_slice_second_residual"))) / float(count), 1),
        "pipe_slice_second_residual_medium_redeclare_retained_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("pipe_slice_second_residual_medium_redeclare_retained"))) / float(count), 1),
        "pipe_slice_dual_full_resolution_rate_pct": round(100.0 * sum(1 for row in selected if bool(row.get("pipe_slice_dual_full_resolution"))) / float(count), 1),
    }


__all__ = [
    "ALLOWED_PATCH_TYPES",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DUAL_RECHECK_OUT_DIR",
    "DEFAULT_FIRST_FIX_OUT_DIR",
    "DEFAULT_MANIFEST_OUT_DIR",
    "DEFAULT_SURFACE_AUDIT_OUT_DIR",
    "DEFAULT_V0331_CLOSEOUT_PATH",
    "DEFAULT_V0332_CLOSEOUT_PATH",
    "PIPE_DUAL_BLUEPRINTS",
    "PIPE_SINGLE_BLUEPRINTS",
    "SCHEMA_PREFIX",
    "anti_noop_rejected",
    "apply_medium_redeclare_discovery_patch",
    "apply_pipe_slice_discovery_patch",
    "apply_repair_step",
    "build_medium_candidate_rhs_symbols",
    "build_mutated_text",
    "build_v0333_dual_specs",
    "build_v0333_single_specs",
    "coverage_target_hit",
    "dual_context_metrics",
    "first_fix_subtype_metrics",
    "handoff_substrate_valid",
    "load_json",
    "norm",
    "now_utc",
    "parse_canonical_rhs_from_repair_step",
    "pipe_slice_target_hit",
    "probe_resolved_result",
    "probe_target_result",
    "rank_medium_rhs_candidates",
    "source_row_for",
    "write_json",
    "write_text",
]
