from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_unknown_library_taskset_v1 import (
    _append_unique,
    _assign_split,
    _build_source_meta,
    _copy_source_model,
    _default_md_path,
    _extract_connects,
    _infer_component_hints,
    _infer_connector_hints,
    _load_json,
    _norm,
    _package_prefixes,
    _ratio,
    _slug,
    _task_provenance_complete,
    _write_json,
    _write_markdown,
    _write_text,
)
from .agent_modelica_wave2_2_coupled_hard_manifest_v1 import (
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_wave2_2_coupled_hard_manifest,
    validate_wave2_2_coupled_hard_manifest,
)


SCHEMA_VERSION = "agent_modelica_wave2_2_coupled_hard_taskset_v1"
DEFAULT_FAILURE_TYPES = (
    "cross_component_parameter_coupling_error",
    "control_loop_sign_semantic_drift",
    "mode_switch_guard_logic_error",
)
FAILURE_METADATA = {
    "cross_component_parameter_coupling_error": {
        "category": "cross_component_coupling",
        "coupling_span": "cross_component",
        "repair_triviality_risk": "low",
        "expected_stage": "simulate",
        "expected_observed_error_type": "semantic_regression",
        "diagnostic_expectation": "cross_component_parameter_coupling_error",
        "mutation_operator": "inject_cross_component_parameter_coupling",
        "mutation_operator_family": "wave2_2_coupled_hard",
        "mock_success_round": 2,
    },
    "control_loop_sign_semantic_drift": {
        "category": "control_loop_semantics",
        "coupling_span": "control_loop",
        "repair_triviality_risk": "low",
        "expected_stage": "simulate",
        "expected_observed_error_type": "semantic_regression",
        "diagnostic_expectation": "control_loop_sign_semantic_drift",
        "mutation_operator": "inject_control_loop_sign_drift",
        "mutation_operator_family": "wave2_2_coupled_hard",
        "mock_success_round": 2,
    },
    "mode_switch_guard_logic_error": {
        "category": "mode_switch_guarding",
        "coupling_span": "control_loop",
        "repair_triviality_risk": "low",
        "expected_stage": "simulate",
        "expected_observed_error_type": "simulate_error",
        "diagnostic_expectation": "mode_switch_guard_logic_error",
        "mutation_operator": "inject_mode_switch_guard_fault",
        "mutation_operator_family": "wave2_2_coupled_hard",
        "mock_success_round": 2,
    },
}


def _extract_source_dependency_objects(connect_rows: list[dict]) -> list[str]:
    objects: list[str] = []
    seen: set[str] = set()
    for row in connect_rows:
        if not isinstance(row, dict):
            continue
        for key in ("lhs", "rhs"):
            endpoint = _norm(row.get(key))
            base = endpoint.split(".", 1)[0].strip()
            if base and base not in seen:
                seen.add(base)
                objects.append(base)
    return objects


def _extract_numeric_signal_endpoints(connect_rows: list[dict]) -> list[str]:
    allowed_suffixes = (".y", ".u", ".pow1", ".pow2", ".pow3", ".y_reset_in")
    endpoints: list[str] = []
    seen: set[str] = set()
    for row in connect_rows:
        if not isinstance(row, dict):
            continue
        for key in ("lhs", "rhs"):
            endpoint = _norm(row.get(key))
            lowered = endpoint.lower()
            if not endpoint or not lowered.endswith(allowed_suffixes):
                continue
            if endpoint not in seen:
                seen.add(endpoint)
                endpoints.append(endpoint)
    return endpoints


def _pick_dependency_endpoints(connect_rows: list[dict], *, count: int) -> list[str]:
    numeric = _extract_numeric_signal_endpoints(connect_rows)
    if len(numeric) >= count:
        return numeric[:count]
    objects = _extract_source_dependency_objects(connect_rows)
    fallback = [f"{name}.y" for name in objects if name]
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*numeric, *fallback]:
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return merged[:count]


def _repair_triviality_risk(
    *,
    mutation_span_count: int,
    delayed_failure_signal: bool,
    source_dependency_count: int,
    uses_existing_equation_context: bool,
    failure_signal_delay_sec: float,
) -> str:
    if mutation_span_count <= 2 or source_dependency_count <= 1 or not uses_existing_equation_context:
        return "high"
    if not delayed_failure_signal or failure_signal_delay_sec < 0.15:
        return "medium"
    return "low"


def _difficulty_rejection_reasons(
    *,
    mutation_span_count: int,
    delayed_failure_signal: bool,
    source_dependency_count: int,
    uses_existing_equation_context: bool,
    failure_signal_delay_sec: float,
) -> list[str]:
    reasons: list[str] = []
    if mutation_span_count <= 2:
        reasons.append("mutation_span_too_narrow")
    if source_dependency_count <= 1:
        reasons.append("insufficient_source_dependency")
    if not uses_existing_equation_context:
        reasons.append("no_existing_equation_context")
    if not delayed_failure_signal or failure_signal_delay_sec < 0.15:
        reasons.append("failure_not_delayed")
    return reasons


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _inject_dynamic_block(model_text: str, *, decl_lines: list[str], eq_lines: list[str]) -> str:
    lines = model_text.splitlines()
    equation_idx = next((idx for idx, line in enumerate(lines) if re.match(r"^\s*equation\s*$", line)), None)
    if equation_idx is None:
        end_idx = next((idx for idx, line in enumerate(lines) if re.match(r"^\s*end\s+[A-Za-z_][A-Za-z0-9_]*\s*;\s*$", line)), len(lines))
        lines.insert(end_idx, "equation")
        equation_idx = end_idx
    for offset, row in enumerate(decl_lines):
        lines.insert(equation_idx + offset, row)
    insert_eq_idx = next((idx + 1 for idx, line in enumerate(lines) if re.match(r"^\s*equation\s*$", line)), len(lines))
    for offset, row in enumerate(eq_lines):
        lines.insert(insert_eq_idx + offset, row)
    return "\n".join(lines) + "\n"


def _replace_first(model_text: str, old: str, new: str) -> tuple[str, bool]:
    if old not in model_text:
        return model_text, False
    return model_text.replace(old, new, 1), True


def _mutate_cross_component_parameter_coupling_error(model_text: str, token: str, dependency_endpoints: list[str]) -> tuple[str, list[dict], str, list[str], float]:
    line_rewrite_candidates = [
        (
            "connect(load.terminal, network.terminal[2])",
            "connect(load.terminal, network.terminal[1])",
            ["load.terminal", "network.terminal[2]", "network.terminal[1]"],
        ),
        (
            "connect(ph_23.y, loaR.Pow2)",
            "connect(ph_1.y, loaR.Pow2)",
            ["ph_23.y", "ph_1.y", "loaR.Pow2"],
        ),
        (
            "connect(cons.y, intWitRes2.u)",
            "connect(ramp.y, intWitRes2.u)",
            ["cons.y", "ramp.y", "intWitRes2.u"],
        ),
        (
            "connect(trapezoid.y, battery.W_setpoint)",
            "connect(trapezoid.y, boundary.f)",
            ["trapezoid.y", "battery.W_setpoint", "boundary.f"],
        ),
    ]
    for old, new, deps in line_rewrite_candidates:
        patched, changed = _replace_first(model_text, old, new)
        if changed:
            objects = [
                {"kind": "source_relation_rewrite", "effect": "cross_component_parameter_coupling_error", "name": old},
                {"kind": "source_relation_rewrite", "effect": "cross_component_parameter_coupling_error", "name": new},
            ]
            objects.extend({"kind": "source_dependency", "effect": "cross_component_parameter_coupling_error", "name": dep} for dep in deps)
            return patched, objects, "gateforge_cross_component_parameter_coupling_error", deps, 0.25

    dep_a = dependency_endpoints[0] if len(dependency_endpoints) > 0 else "time"
    dep_b = dependency_endpoints[1] if len(dependency_endpoints) > 1 else dep_a
    decl = [
        f"  parameter Real __gf_cross_gain_{token} = -4.0; // gateforge_cross_component_parameter_coupling_error",
        f"  parameter Real __gf_cross_trigger_time_{token} = 0.25; // gateforge_cross_component_parameter_coupling_error",
        f"  Real __gf_cross_a_{token}(start=0.02);",
        f"  Real __gf_cross_b_{token}(start=0.01);",
    ]
    eq = [
        f"  der(__gf_cross_a_{token}) = 1e-4*({dep_a}) - __gf_cross_a_{token} + __gf_cross_b_{token}; // gateforge_cross_component_parameter_coupling_error",
        f"  der(__gf_cross_b_{token}) = 1e-4*(__gf_cross_gain_{token}*({dep_b})) - __gf_cross_b_{token} - 0.5*__gf_cross_a_{token}; // gateforge_cross_component_parameter_coupling_error",
        f'  assert(time < __gf_cross_trigger_time_{token} or abs(__gf_cross_a_{token} - __gf_cross_b_{token}) < 0.02, "gateforge_cross_component_parameter_coupling_error_{token}");',
    ]
    patched = _inject_dynamic_block(model_text, decl_lines=decl, eq_lines=eq)
    objects = [
        {"kind": "cross_component_parameter", "effect": "cross_component_parameter_coupling_error", "name": f"__gf_cross_gain_{token}"},
        {"kind": "cross_component_trigger", "effect": "cross_component_parameter_coupling_error", "name": f"__gf_cross_trigger_time_{token}"},
        {"kind": "cross_component_state", "effect": "cross_component_parameter_coupling_error", "name": f"__gf_cross_a_{token}"},
        {"kind": "cross_component_state", "effect": "cross_component_parameter_coupling_error", "name": f"__gf_cross_b_{token}"},
        {"kind": "source_dependency", "effect": "cross_component_parameter_coupling_error", "name": dep_a},
        {"kind": "source_dependency", "effect": "cross_component_parameter_coupling_error", "name": dep_b},
    ]
    return patched, objects, "gateforge_cross_component_parameter_coupling_error", [dep_a, dep_b], 0.25


def _mutate_control_loop_sign_semantic_drift(model_text: str, token: str, dependency_endpoints: list[str]) -> tuple[str, list[dict], str, list[str], float]:
    parameter_rewrite_candidates = [
        (
            "height=5000",
            "height=-5000",
            ["load_inputs.y", "load.Pow1"],
        ),
        (
            "amplitude=2000",
            "amplitude=-2000",
            ["ph_1.y", "loaR.Pow1"],
        ),
        (
            "k=0.5",
            "k=-0.5",
            ["cons.y", "intWitRes1.u"],
        ),
        (
            "amplitude=1e6",
            "amplitude=-1e6",
            ["trapezoid.y", "battery.W_setpoint"],
        ),
    ]
    for old, new, deps in parameter_rewrite_candidates:
        patched, changed = _replace_first(model_text, old, new)
        if changed:
            objects = [
                {"kind": "source_parameter_rewrite", "effect": "control_loop_sign_semantic_drift", "name": old},
                {"kind": "source_parameter_rewrite", "effect": "control_loop_sign_semantic_drift", "name": new},
            ]
            objects.extend({"kind": "source_dependency", "effect": "control_loop_sign_semantic_drift", "name": dep} for dep in deps)
            return patched, objects, "gateforge_control_loop_sign_semantic_drift", deps, 0.55

    dep_drive = dependency_endpoints[0] if len(dependency_endpoints) > 0 else "time"
    dep_feedback = dependency_endpoints[1] if len(dependency_endpoints) > 1 else dep_drive
    decl = [
        f"  parameter Real __gf_loop_gain_{token} = 2.5; // gateforge_control_loop_sign_semantic_drift",
        f"  parameter Real __gf_loop_trigger_time_{token} = 0.55; // gateforge_control_loop_sign_semantic_drift",
        f"  Real __gf_loop_state_{token}(start=0.01);",
        f"  Real __gf_loop_feedback_{token}(start=0.0);",
    ]
    eq = [
        f"  der(__gf_loop_feedback_{token}) = -2e-4*({dep_drive}) + __gf_loop_gain_{token}*__gf_loop_state_{token} - 0.4*__gf_loop_feedback_{token}; // gateforge_control_loop_sign_semantic_drift",
        f"  der(__gf_loop_state_{token}) = __gf_loop_state_{token} + __gf_loop_feedback_{token} + 1e-4*({dep_feedback}); // gateforge_control_loop_sign_semantic_drift",
        f'  assert(time < __gf_loop_trigger_time_{token} or __gf_loop_state_{token} < 0.08, "gateforge_control_loop_sign_semantic_drift_{token}");',
    ]
    patched = _inject_dynamic_block(model_text, decl_lines=decl, eq_lines=eq)
    objects = [
        {"kind": "control_loop_gain", "effect": "control_loop_sign_semantic_drift", "name": f"__gf_loop_gain_{token}"},
        {"kind": "control_loop_trigger", "effect": "control_loop_sign_semantic_drift", "name": f"__gf_loop_trigger_time_{token}"},
        {"kind": "control_loop_state", "effect": "control_loop_sign_semantic_drift", "name": f"__gf_loop_state_{token}"},
        {"kind": "control_loop_feedback", "effect": "control_loop_sign_semantic_drift", "name": f"__gf_loop_feedback_{token}"},
        {"kind": "source_dependency", "effect": "control_loop_sign_semantic_drift", "name": dep_drive},
        {"kind": "source_dependency", "effect": "control_loop_sign_semantic_drift", "name": dep_feedback},
    ]
    return patched, objects, "gateforge_control_loop_sign_semantic_drift", [dep_drive, dep_feedback], 0.55


def _mutate_mode_switch_guard_logic_error(model_text: str, token: str, dependency_endpoints: list[str]) -> tuple[str, list[dict], str, list[str], float]:
    guard_rewrite_candidates = [
        (
            "startTime=0.25",
            "startTime=0.0",
            ["load_inputs.y", "load.Pow1"],
        ),
        (
            "duration=0.5",
            "duration=0.05",
            ["load_inputs.y", "load.Pow2"],
        ),
        (
            "period=0.2",
            "period=0.02",
            ["booleanPulse.y", "intWitRes2.trigger"],
        ),
        (
            "width=50",
            "width=5",
            ["booleanPulse.y", "intWitRes2.trigger"],
        ),
        (
            "startTime=1000",
            "startTime=0",
            ["trapezoid.y", "battery.W_setpoint"],
        ),
        (
            "period=4000",
            "period=400",
            ["trapezoid.y", "battery.W_setpoint"],
        ),
    ]
    patched = model_text
    used_deps: list[str] = []
    changed_rules: list[tuple[str, str]] = []
    changed_count = 0
    for old, new, deps in guard_rewrite_candidates:
        if changed_count >= 2:
            break
        updated, changed = _replace_first(patched, old, new)
        if changed:
            patched = updated
            changed_count += 1
            changed_rules.append((old, new))
            for dep in deps:
                if dep not in used_deps:
                    used_deps.append(dep)
    if changed_count >= 1:
        objects = []
        for old, new in changed_rules:
            objects.append({"kind": "source_guard_rewrite", "effect": "mode_switch_guard_logic_error", "name": old})
            objects.append({"kind": "source_guard_rewrite", "effect": "mode_switch_guard_logic_error", "name": new})
        objects.extend(
            {"kind": "source_dependency", "effect": "mode_switch_guard_logic_error", "name": dep}
            for dep in used_deps
        )
        return patched, objects, "gateforge_mode_switch_guard_logic_error", used_deps, 0.35 if changed_count == 1 else 0.55

    dep_guard = dependency_endpoints[0] if len(dependency_endpoints) > 0 else "time"
    dep_ref = dependency_endpoints[1] if len(dependency_endpoints) > 1 else dep_guard
    decl = [
        f"  parameter Real __gf_guard_threshold_{token} = 0.02; // gateforge_mode_switch_guard_logic_error",
        f"  parameter Real __gf_guard_release_time_{token} = 0.55; // gateforge_mode_switch_guard_logic_error",
        f"  Real __gf_mode_state_{token}(start=0.0);",
    ]
    eq = [
        f"  der(__gf_mode_state_{token}) = 1e-4*abs(({dep_guard}) - ({dep_ref})); // gateforge_mode_switch_guard_logic_error",
        f'  when time > 0.2 and __gf_mode_state_{token} > __gf_guard_threshold_{token} and time < __gf_guard_release_time_{token} then assert(false, "gateforge_mode_switch_guard_logic_error_{token}"); end when;',
    ]
    patched = _inject_dynamic_block(model_text, decl_lines=decl, eq_lines=eq)
    objects = [
        {"kind": "guard_threshold", "effect": "mode_switch_guard_logic_error", "name": f"__gf_guard_threshold_{token}"},
        {"kind": "guard_release_time", "effect": "mode_switch_guard_logic_error", "name": f"__gf_guard_release_time_{token}"},
        {"kind": "mode_state", "effect": "mode_switch_guard_logic_error", "name": f"__gf_mode_state_{token}"},
        {"kind": "source_dependency", "effect": "mode_switch_guard_logic_error", "name": dep_guard},
        {"kind": "source_dependency", "effect": "mode_switch_guard_logic_error", "name": dep_ref},
    ]
    return patched, objects, "gateforge_mode_switch_guard_logic_error", [dep_guard, dep_ref], 0.55


def build_wave2_2_coupled_hard_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
    exclude_task_ids_json: str | None = None,
) -> dict:
    payload = load_wave2_2_coupled_hard_manifest(manifest_path)
    libraries, manifest_reasons = validate_wave2_2_coupled_hard_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    reasons = list(manifest_reasons)
    selected_models: list[tuple[dict, dict]] = []
    for library in libraries:
        for model in library.get("allowed_models") or []:
            if isinstance(model, dict):
                selected_models.append((library, model))

    copied_source_paths: dict[str, str] = {}
    taskset_tasks: list[dict] = []
    counts_by_failure: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_library: dict[str, int] = {}
    counts_by_coupling_span: dict[str, int] = {}
    counts_by_repair_triviality_risk: dict[str, int] = {}
    diagnostic_expectation_by_failure_type: dict[str, dict] = {}
    rejection_reasons: dict[str, int] = {}
    rejected_candidates: list[dict] = []

    excluded_task_ids: set[str] = set()
    if exclude_task_ids_json:
        exclude_payload = _load_json(exclude_task_ids_json)
        for item in exclude_payload.get("task_ids") or []:
            normalized = _norm(item)
            if normalized:
                excluded_task_ids.add(normalized)

    for library, model in selected_models:
        model_path = Path(_norm(model.get("model_path")))
        source_text = model_path.read_text(encoding="utf-8", errors="ignore")
        connect_rows = _extract_connects(source_text)
        library_id = _norm(library.get("library_id")).lower()
        model_id = _norm(model.get("model_id")).lower()
        package_name = _norm(library.get("package_name"))
        source_rel = f"{library_id}/{model_id}.mo"
        copied_source_path = source_models_dir / source_rel
        if str(model_path) not in copied_source_paths:
            _copy_source_model(model_path, copied_source_path)
            copied_source_paths[str(model_path)] = str(copied_source_path.resolve())
        source_model_path = copied_source_paths[str(model_path)]
        source_meta = _build_source_meta(manifest_real_path, library, model)
        source_meta["seen_risk_band"] = _norm(model.get("seen_risk_band") or library.get("seen_risk_band")).lower()
        source_meta["source_type"] = _norm(model.get("source_type") or library.get("source_type")).lower()

        library_hints: list[str] = []
        seen_lib: set[str] = set()
        for item in [library_id, package_name, source_meta.get("source_library"), *(_package_prefixes(package_name))]:
            _append_unique(library_hints, seen_lib, item)
        component_hints = _infer_component_hints(source_text, _norm(model.get("qualified_model_name")))
        component_seen = set(component_hints)
        for item in model.get("component_hints") or []:
            _append_unique(component_hints, component_seen, item)
        connector_hints = _infer_connector_hints(connect_rows, [str(x) for x in (model.get("connector_hints") or []) if isinstance(x, str)])
        domain = _norm(library.get("domain")).lower()
        scale_hint = _norm(model.get("scale_hint") or library.get("scale_hint") or "small").lower()
        seen_risk_band = _norm(model.get("seen_risk_band") or library.get("seen_risk_band")).lower()
        source_type = _norm(model.get("source_type") or library.get("source_type")).lower()

        for failure_type in failure_types:
            meta = FAILURE_METADATA[failure_type]
            token = _slug(_sha256_text(f"{library_id}:{model_id}:{failure_type}")[:10]) or "cpl"
            dependency_endpoints = _pick_dependency_endpoints(connect_rows, count=2)
            if failure_type == "cross_component_parameter_coupling_error":
                mutated_text, mutated_objects, mutation_excerpt, used_dependencies, failure_signal_delay_sec = _mutate_cross_component_parameter_coupling_error(source_text, token, dependency_endpoints)
            elif failure_type == "control_loop_sign_semantic_drift":
                mutated_text, mutated_objects, mutation_excerpt, used_dependencies, failure_signal_delay_sec = _mutate_control_loop_sign_semantic_drift(source_text, token, dependency_endpoints)
            else:
                mutated_text, mutated_objects, mutation_excerpt, used_dependencies, failure_signal_delay_sec = _mutate_mode_switch_guard_logic_error(source_text, token, dependency_endpoints)
            task_id = f"wave2_2_{library_id}_{model_id}_{failure_type}"
            if task_id in excluded_task_ids:
                rejected_candidates.append(
                    {
                        "task_id": task_id,
                        "failure_type": failure_type,
                        "library_id": library_id,
                        "model_id": model_id,
                        "rejection_reasons": ["excluded_by_easy_task_exclusions"],
                    }
                )
                rejection_reasons["excluded_by_easy_task_exclusions"] = int(rejection_reasons.get("excluded_by_easy_task_exclusions", 0)) + 1
                continue
            mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
            _write_text(mutated_path, mutated_text)
            mutation_span_count = len(mutated_objects)
            delayed_failure_signal = True
            source_dependency_count = len([item for item in used_dependencies if _norm(item)])
            uses_existing_equation_context = source_dependency_count >= 2
            repair_triviality_risk = _repair_triviality_risk(
                mutation_span_count=mutation_span_count,
                delayed_failure_signal=delayed_failure_signal,
                source_dependency_count=source_dependency_count,
                uses_existing_equation_context=uses_existing_equation_context,
                failure_signal_delay_sec=failure_signal_delay_sec,
            )
            task_rejection_reasons = _difficulty_rejection_reasons(
                mutation_span_count=mutation_span_count,
                delayed_failure_signal=delayed_failure_signal,
                source_dependency_count=source_dependency_count,
                uses_existing_equation_context=uses_existing_equation_context,
                failure_signal_delay_sec=failure_signal_delay_sec,
            )
            if task_rejection_reasons:
                rejected_candidates.append(
                    {
                        "task_id": task_id,
                        "failure_type": failure_type,
                        "library_id": library_id,
                        "model_id": model_id,
                        "repair_triviality_risk": repair_triviality_risk,
                        "mutation_span_count": mutation_span_count,
                        "delayed_failure_signal": delayed_failure_signal,
                        "failure_signal_delay_sec": failure_signal_delay_sec,
                        "source_dependency_count": source_dependency_count,
                        "uses_existing_equation_context": uses_existing_equation_context,
                        "source_dependency_objects": list(used_dependencies),
                        "rejection_reasons": list(task_rejection_reasons),
                    }
                )
                for reason in task_rejection_reasons:
                    rejection_reasons[reason] = int(rejection_reasons.get(reason, 0)) + 1
                continue
            task = {
                "task_id": task_id,
                "scale": scale_hint,
                "failure_type": failure_type,
                "category": meta["category"],
                "coupling_span": meta["coupling_span"],
                "repair_triviality_risk": repair_triviality_risk,
                "mutation_span_count": mutation_span_count,
                "delayed_failure_signal": delayed_failure_signal,
                "compile_pass_expected": True,
                "simulate_phase_required": True,
                "trivial_restore_guard": bool(
                    delayed_failure_signal
                    and uses_existing_equation_context
                    and source_dependency_count >= 2
                    and mutation_span_count >= 3
                ),
                "expected_stage": meta["expected_stage"],
                "expected_observed_error_type": meta["expected_observed_error_type"],
                "diagnostic_expectation": meta["diagnostic_expectation"],
                "mutation_operator": meta["mutation_operator"],
                "mutation_operator_family": meta["mutation_operator_family"],
                "mock_success_round": meta["mock_success_round"],
                "mock_round_duration_sec": 30,
                "source_dependency_count": source_dependency_count,
                "uses_existing_equation_context": uses_existing_equation_context,
                "failure_signal_delay_sec": failure_signal_delay_sec,
                "source_dependency_objects": list(used_dependencies),
                "source_model_path": str(Path(source_model_path).resolve()),
                "mutated_model_path": str(mutated_path.resolve()),
                "source_meta": dict(source_meta),
                "source_library": library_id,
                "domain": domain,
                "domains": [domain] if domain else [],
                "library_hints": list(library_hints),
                "component_hints": list(component_hints),
                "connector_hints": list(connector_hints),
                "model_hint": _norm(model.get("qualified_model_name")),
                "repro_command": f"omc {str(mutated_path.resolve())}",
                "mutated_objects": mutated_objects,
                "mutation_excerpt": mutation_excerpt,
                "seen_risk_band": seen_risk_band,
                "source_type": source_type,
            }
            taskset_tasks.append(task)
            counts_by_failure[failure_type] = int(counts_by_failure.get(failure_type, 0)) + 1
            counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1
            counts_by_coupling_span[meta["coupling_span"]] = int(counts_by_coupling_span.get(meta["coupling_span"], 0)) + 1
            counts_by_repair_triviality_risk[repair_triviality_risk] = int(counts_by_repair_triviality_risk.get(repair_triviality_risk, 0)) + 1
            diagnostic_expectation_by_failure_type[failure_type] = {
                "expected_stage": meta["expected_stage"],
                "expected_observed_error_type": meta["expected_observed_error_type"],
                "coupling_span": meta["coupling_span"],
                "diagnostic_expectation": meta["diagnostic_expectation"],
            }

    taskset_tasks = sorted(taskset_tasks, key=lambda row: _norm(row.get("task_id")))
    for task in taskset_tasks:
        task["split"] = _assign_split(task, holdout_ratio=holdout_ratio, seed=seed)
    if taskset_tasks and not any(_norm(task.get("split")) == "holdout" for task in taskset_tasks):
        taskset_tasks[0]["split"] = "holdout"

    provenance_complete_count = len([task for task in taskset_tasks if _task_provenance_complete(task)])
    status = "PASS"
    if len(taskset_tasks) < 18:
        status = "FAIL"
        reasons.append("task_count_below_minimum")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": "wave2_2_coupled_hard_frozen",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_real_path,
        "failure_types": list(failure_types),
        "total_tasks": len(taskset_tasks),
        "library_count": len({str(task.get('source_library') or '').strip() for task in taskset_tasks if str(task.get('source_library') or '').strip()}),
        "model_count": len(selected_models),
        "counts_by_library": counts_by_library,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_coupling_span": counts_by_coupling_span,
        "counts_by_repair_triviality_risk": counts_by_repair_triviality_risk,
        "diagnostic_expectation_by_failure_type": diagnostic_expectation_by_failure_type,
        "provenance_completeness_pct": _ratio(provenance_complete_count, len(taskset_tasks)),
        "library_hints_nonempty_pct": _ratio(len([task for task in taskset_tasks if task.get("library_hints")]), len(taskset_tasks)),
        "delayed_failure_signal_pct": _ratio(len([task for task in taskset_tasks if task.get("delayed_failure_signal")]), len(taskset_tasks)),
        "rejected_candidate_count": len(rejected_candidates),
        "rejection_reasons": rejection_reasons,
        "taskset_unfrozen_path": str((out_root / "taskset_unfrozen.json").resolve()),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
        "task_construction_rejections_path": str((out_root / "task_construction_rejections.json").resolve()),
        "reasons": sorted(set(reasons)),
    }
    frozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "wave2_2_coupled_hard_frozen", "tasks": taskset_tasks}
    unfrozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "wave2_2_coupled_hard_unfrozen", "tasks": taskset_tasks}
    _write_json(out_root / "taskset_unfrozen.json", unfrozen_payload)
    _write_json(out_root / "taskset_frozen.json", frozen_payload)
    _write_json(out_root / "manifest.json", payload)
    _write_json(
        out_root / "task_construction_rejections.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "rejected_candidate_count": len(rejected_candidates),
            "rejection_reasons": rejection_reasons,
            "candidates": rejected_candidates,
        },
    )
    _write_json(out_root / "summary.json", summary)
    md = [
        "# Wave2.2 Coupled-Hard Taskset",
        "",
        f"- status: `{status}`",
        f"- total_tasks: `{len(taskset_tasks)}`",
        f"- counts_by_failure_type: `{json.dumps(counts_by_failure, sort_keys=True)}`",
        f"- counts_by_coupling_span: `{json.dumps(counts_by_coupling_span, sort_keys=True)}`",
    ]
    markdown_path = _default_md_path(str((out_root / "summary.json").resolve()))
    Path(markdown_path).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "total_tasks": len(taskset_tasks), "counts_by_failure_type": counts_by_failure}))
    if status != "PASS":
        raise SystemExit(1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave2.2 coupled-hard frozen taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_wave2_2_coupled_hard_taskset_v1")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_wave2_2_coupled_hard_taskset_v1")
    parser.add_argument("--exclude-task-ids-json")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    build_wave2_2_coupled_hard_taskset(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed),
        exclude_task_ids_json=str(args.exclude_task_ids_json) if args.exclude_task_ids_json else None,
    )


if __name__ == "__main__":
    main()
