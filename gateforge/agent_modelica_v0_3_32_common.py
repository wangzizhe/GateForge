from __future__ import annotations

import re
from pathlib import Path

from .agent_modelica_v0_3_20_common import load_json, norm, write_json, write_text
from .agent_modelica_v0_3_21_common import now_utc
from .agent_modelica_v0_3_29_common import apply_repair_step, build_mutated_text, run_dry_run
from .agent_modelica_v0_3_30_common import (
    apply_medium_redeclare_discovery_patch,
    build_medium_candidate_rhs_symbols,
    medium_redeclare_target_hit,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
)
from .agent_modelica_v0_3_31_common import build_v0331_source_specs


SCHEMA_PREFIX = "agent_modelica_v0_3_32"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TRIAGE_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_32_pipe_viability_triage_current"
DEFAULT_ENTRY_SPEC_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_32_pipe_entry_spec_current"
DEFAULT_FIRST_FIX_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_32_pipe_first_fix_evidence_current"
DEFAULT_DISCOVERY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_32_pipe_discovery_probe_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_32_closeout_current"

DEFAULT_V0331_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_closeout_current" / "summary.json"
DEFAULT_V0331_HANDOFF_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_31_surface_export_audit_current" / "active_taskset.json"

PIPE_TARGET_STAGE = "check"
PIPE_TARGET_ERROR_TYPE = "model_check_error"
PIPE_ACCEPTED_TARGET_SUBSIGNATURES = [
    "stage_2_structural_balance_reference|undefined_symbol",
    "stage_2_structural_balance_reference|compile_failure_unknown",
]
ALLOWED_PATCH_TYPES = [
    "insert_redeclare_package_medium",
    "replace_redeclare_clause",
    "replace_medium_package_symbol",
]


def fixture_pipe_target_result(*, phase: str = "target_hit", wrong_symbol: str = "MediumPipe") -> dict:
    if phase == "resolved":
        return {
            "return_code": 0,
            "check_model_pass": True,
            "output_excerpt": "Check of model passed.",
            "error_type": "none",
            "error_subtype": "none",
            "stage": "none",
            "observed_phase": "check",
            "reason": "",
            "error_signature": "",
        }
    excerpt = (
        f'true true "" "[/workspace/model.mo:5:50-5:77:writable] Error: Base class {wrong_symbol} not found in scope FixtureModel. '
        '[/workspace/.omc_home/.openmodelica/libraries/Modelica 4.1.0+maint.om/Fluid/Interfaces.mo:13:5-14:68:writable] '
        'Error: Class Medium.MassFlowRate not found in scope FluidPort. "'
    )
    return {
        "return_code": 1,
        "check_model_pass": False,
        "output_excerpt": excerpt,
        "error_type": "model_check_error",
        "error_subtype": "undefined_symbol",
        "stage": "check",
        "observed_phase": "check",
        "reason": "model check failed",
        "error_signature": excerpt,
    }


def _wrong_symbol_for(component_name: str) -> str:
    component = norm(component_name)
    if component.startswith("port_"):
        return "MediumPort"
    return "MediumPipe"


def _replace_rhs_symbol(declaration: str, wrong_symbol: str) -> str:
    return norm(declaration).replace("redeclare package Medium = Medium", f"redeclare package Medium = {norm(wrong_symbol)}", 1)


def _source_map() -> dict[str, dict]:
    selected_ids = {
        "medium_port_pipe_tank",
        "medium_port_pipe_volume",
        "medium_boundary_pipe_volume_sink",
        "medium_boundary_pipe_tank_sink",
        "medium_source_pipe_tank_ports",
    }
    rows = [row for row in build_v0331_source_specs() if norm(row.get("source_id")) in selected_ids]
    return {norm(row.get("source_id")): row for row in rows}


def build_v0332_source_specs() -> list[dict]:
    return list(_source_map().values())


def source_row_for(source_id: str) -> dict:
    return dict(_source_map().get(norm(source_id)) or {})


def component_variant(source_id: str, component_name: str) -> dict:
    source = source_row_for(source_id)
    for row in list(source.get("component_variants") or []):
        if norm(row.get("component_name")) == norm(component_name):
            return dict(row)
    return {}


def build_pipe_single_spec(source_id: str, component_name: str) -> dict:
    source = source_row_for(source_id)
    variant = component_variant(source_id, component_name)
    declaration = norm(variant.get("declaration"))
    wrong_symbol = _wrong_symbol_for(component_name)
    mutated_declaration = _replace_rhs_symbol(declaration, wrong_symbol)
    if norm(component_name) == "pipe":
        pattern_id = "pipe_medium_symbol_replace"
    elif norm(component_name) == "port_a":
        pattern_id = "fluid_port_a_medium_symbol_replace"
    else:
        pattern_id = "fluid_port_b_medium_symbol_replace"
    return {
        "task_id": f"v0332_single_{source_id}_wrong_{component_name}",
        "source_id": norm(source_id),
        "model_name": norm(source.get("model_name")),
        "complexity_tier": norm(source.get("complexity_tier")) or "medium",
        "component_name": norm(component_name),
        "component_subtype": norm(variant.get("subtype")),
        "pattern_id": pattern_id,
        "patch_type": "replace_medium_package_symbol",
        "allowed_patch_types": ["replace_medium_package_symbol"],
        "wrong_symbol": wrong_symbol,
        "correct_target": f"{component_name}.redeclare package Medium = Medium",
        "injection_replacements": [(declaration, mutated_declaration)],
        "repair_steps": [
            {
                "patch_type": "replace_medium_package_symbol",
                "match_text": mutated_declaration,
                "replacement_text": declaration,
            }
        ],
    }


def build_pipe_dual_spec(source_id: str, first_component: str, second_component: str) -> dict:
    source = source_row_for(source_id)
    first = component_variant(source_id, first_component)
    second = component_variant(source_id, second_component)
    first_declaration = norm(first.get("declaration"))
    second_declaration = norm(second.get("declaration"))
    first_wrong = _replace_rhs_symbol(first_declaration, _wrong_symbol_for(first_component))
    second_wrong = _replace_rhs_symbol(second_declaration, _wrong_symbol_for(second_component))
    return {
        "task_id": f"v0332_dual_{source_id}_{first_component}_then_{second_component}",
        "source_id": norm(source_id),
        "model_name": norm(source.get("model_name")),
        "complexity_tier": norm(source.get("complexity_tier")) or "medium",
        "component_name": f"{first_component}->{second_component}",
        "component_subtype": "pipe_or_local_fluid_interface_like",
        "pattern_id": "pipe_dual_medium_symbol_replace",
        "allowed_patch_types": ["replace_medium_package_symbol"],
        "repair_steps": [
            {
                "patch_type": "replace_medium_package_symbol",
                "match_text": first_wrong,
                "replacement_text": first_declaration,
            },
            {
                "patch_type": "replace_medium_package_symbol",
                "match_text": second_wrong,
                "replacement_text": second_declaration,
            },
        ],
        "injection_replacements": [
            (first_declaration, first_wrong),
            (second_declaration, second_wrong),
        ],
    }


PIPE_PATTERN_SPECS = [
    {
        "pattern_id": "pipe_medium_symbol_replace",
        "source_id": "medium_port_pipe_tank",
        "component_name": "pipe",
        "complexity_tier": "medium",
        "dual_precheck_components": ("pipe", "port_a"),
    },
    {
        "pattern_id": "fluid_port_a_medium_symbol_replace",
        "source_id": "medium_port_pipe_tank",
        "component_name": "port_a",
        "complexity_tier": "medium",
        "dual_precheck_components": ("port_a", "port_b"),
    },
    {
        "pattern_id": "fluid_port_b_medium_symbol_replace",
        "source_id": "medium_port_pipe_tank",
        "component_name": "port_b",
        "complexity_tier": "medium",
        "dual_precheck_components": ("port_b", "port_a"),
    },
]

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
    ("medium_port_pipe_tank", "pipe", "port_a"),
    ("medium_port_pipe_tank", "port_a", "port_b"),
    ("medium_port_pipe_volume", "pipe", "port_a"),
    ("medium_port_pipe_volume", "port_a", "port_b"),
    ("medium_source_pipe_tank_ports", "pipe", "port_a"),
    ("medium_source_pipe_tank_ports", "port_a", "port_b"),
]


def build_v0332_single_specs() -> list[dict]:
    return [build_pipe_single_spec(source_id, component_name) for source_id, component_name in PIPE_SINGLE_BLUEPRINTS]


def build_v0332_dual_specs() -> list[dict]:
    return [build_pipe_dual_spec(source_id, first_component, second_component) for source_id, first_component, second_component in PIPE_DUAL_BLUEPRINTS]


def pipe_target_signature(result: dict) -> str:
    return f"stage_2_structural_balance_reference|{norm(result.get('error_subtype'))}"


def pipe_slice_target_hit(result: dict) -> bool:
    if norm(result.get("error_type")) != PIPE_TARGET_ERROR_TYPE or norm(result.get("stage")) != PIPE_TARGET_STAGE:
        return False
    if medium_redeclare_target_hit(result):
        return True
    excerpt = norm(result.get("output_excerpt")).lower()
    return norm(result.get("error_subtype")) == "undefined_symbol" and any(
        token in excerpt
        for token in (
            "base class mediumpipe not found",
            "base class mediumport not found",
            "class medium.massflowrate not found in scope fluidport",
        )
    )


def anti_noop_rejected(result: dict) -> bool:
    return bool(result.get("check_model_pass"))


def bounded_medium_target_family(result: dict) -> str:
    if medium_redeclare_target_hit(result):
        return "bounded_medium_compile_failure"
    if pipe_slice_target_hit(result):
        return "bounded_medium_undefined_symbol"
    return ""


def handoff_substrate_valid(v0331_closeout: dict) -> bool:
    decision = norm(((v0331_closeout.get("conclusion") or {}).get("version_decision")))
    return decision in {
        "stage2_medium_redeclare_discovery_coverage_partially_ready",
        "stage2_medium_redeclare_discovery_coverage_ready",
    }


def probe_target_result(*, model_name: str, model_text: str, wrong_symbol: str, use_fixture_only: bool) -> dict:
    if use_fixture_only:
        return fixture_pipe_target_result(phase="target_hit", wrong_symbol=wrong_symbol)
    return run_dry_run(model_name, model_text)


def probe_resolved_result(*, model_name: str, model_text: str, use_fixture_only: bool) -> dict:
    if use_fixture_only:
        return fixture_pipe_target_result(phase="resolved")
    return run_dry_run(model_name, model_text)


def apply_pipe_slice_discovery_patch(*, current_text: str, step: dict, selected_rhs_symbol: str) -> tuple[str, dict]:
    current = norm(current_text)
    match_text = norm(step.get("match_text"))
    selected = norm(selected_rhs_symbol)
    canonical_rhs_symbol = parse_canonical_rhs_from_repair_step(step)
    if not match_text:
        return current, {"applied": False, "reason": "missing_match_text", "selected_rhs_symbol": selected, "canonical_rhs_symbol": canonical_rhs_symbol}
    if match_text not in current:
        return current, {"applied": False, "reason": "match_text_not_found", "selected_rhs_symbol": selected, "canonical_rhs_symbol": canonical_rhs_symbol}
    if "redeclare package Medium =" not in match_text or not selected:
        return current, {"applied": False, "reason": "unsupported_match_text", "selected_rhs_symbol": selected, "canonical_rhs_symbol": canonical_rhs_symbol}
    replacement_text = re.sub(
        r"(redeclare\s+package\s+Medium\s*=\s*)([A-Za-z_][A-Za-z0-9_\.]*)",
        rf"\1{selected}",
        match_text,
        count=1,
    )
    updated = current.replace(match_text, replacement_text, 1)
    return updated, {
        "applied": updated != current,
        "reason": "applied_discovery_patch" if updated != current else "text_unchanged_after_patch",
        "selected_rhs_symbol": selected,
        "canonical_rhs_symbol": canonical_rhs_symbol,
        "replacement_text": replacement_text,
    }


__all__ = [
    "ALLOWED_PATCH_TYPES",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DISCOVERY_OUT_DIR",
    "DEFAULT_ENTRY_SPEC_OUT_DIR",
    "DEFAULT_FIRST_FIX_OUT_DIR",
    "DEFAULT_TRIAGE_OUT_DIR",
    "DEFAULT_V0331_CLOSEOUT_PATH",
    "DEFAULT_V0331_HANDOFF_TASKSET_PATH",
    "PIPE_ACCEPTED_TARGET_SUBSIGNATURES",
    "PIPE_PATTERN_SPECS",
    "SCHEMA_PREFIX",
    "anti_noop_rejected",
    "apply_medium_redeclare_discovery_patch",
    "apply_repair_step",
    "bounded_medium_target_family",
    "build_medium_candidate_rhs_symbols",
    "build_mutated_text",
    "build_pipe_dual_spec",
    "build_pipe_single_spec",
    "build_v0332_dual_specs",
    "build_v0332_single_specs",
    "build_v0332_source_specs",
    "component_variant",
    "apply_pipe_slice_discovery_patch",
    "fixture_pipe_target_result",
    "handoff_substrate_valid",
    "load_json",
    "medium_redeclare_target_hit",
    "norm",
    "now_utc",
    "parse_canonical_rhs_from_repair_step",
    "pipe_slice_target_hit",
    "pipe_target_signature",
    "probe_resolved_result",
    "probe_target_result",
    "rank_medium_rhs_candidates",
    "run_dry_run",
    "source_row_for",
    "write_json",
    "write_text",
]
