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
from .agent_modelica_wave2_1_harder_dynamics_manifest_v1 import (
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_wave2_1_harder_dynamics_manifest,
    validate_wave2_1_harder_dynamics_manifest,
)


SCHEMA_VERSION = "agent_modelica_wave2_1_harder_dynamics_taskset_v1"
DEFAULT_FAILURE_TYPES = (
    "solver_sensitive_simulate_failure",
    "event_logic_error",
    "semantic_drift_after_compile_pass",
)
FAILURE_METADATA = {
    "solver_sensitive_simulate_failure": {
        "category": "dynamic_solver_sensitivity",
        "dynamic_error_family": "solver_dynamics",
        "expected_stage": "simulate",
        "expected_observed_error_type": "numerical_instability",
        "diagnostic_expectation": "solver_sensitive_simulate_failure",
        "mutation_operator": "inject_ultra_stiff_dynamics",
        "mutation_operator_family": "wave2_1_dynamics",
        "mock_success_round": 2,
    },
    "event_logic_error": {
        "category": "event_mode_switching",
        "dynamic_error_family": "event_logic",
        "expected_stage": "simulate",
        "expected_observed_error_type": "simulate_error",
        "diagnostic_expectation": "event_logic_error",
        "mutation_operator": "inject_event_chattering_threshold",
        "mutation_operator_family": "wave2_1_dynamics",
        "mock_success_round": 2,
    },
    "semantic_drift_after_compile_pass": {
        "category": "behavioral_semantics",
        "dynamic_error_family": "semantic_drift",
        "expected_stage": "simulate",
        "expected_observed_error_type": "semantic_regression",
        "diagnostic_expectation": "semantic_drift_after_compile_pass",
        "mutation_operator": "inject_sign_flip_dynamics",
        "mutation_operator_family": "wave2_1_dynamics",
        "mock_success_round": 2,
    },
}


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


def _mutate_solver_sensitive_simulate_failure(model_text: str, token: str) -> tuple[str, list[dict], str]:
    decl = [
        f"  parameter Real __gf_tau_{token} = 1e-12; // gateforge_solver_sensitive_simulate_failure",
        f"  Real __gf_state_{token}(start=1.0);",
    ]
    eq = [
        f"  der(__gf_state_{token}) = (1.0 - __gf_state_{token}) / __gf_tau_{token}; // gateforge_solver_sensitive_simulate_failure",
    ]
    patched = _inject_dynamic_block(model_text, decl_lines=decl, eq_lines=eq)
    objects = [{"kind": "solver_sensitive_dynamics", "effect": "solver_sensitive_simulate_failure", "name": f"__gf_state_{token}"}]
    return patched, objects, "gateforge_solver_sensitive_simulate_failure"


def _mutate_event_logic_error(model_text: str, token: str) -> tuple[str, list[dict], str]:
    decl = [f"  Real __gf_event_state_{token}(start=0.0);"]
    eq = [
        f"  der(__gf_event_state_{token}) = 1.0; // gateforge_event_logic_error",
        f'  when __gf_event_state_{token} > 0.5 then assert(false, "gateforge_event_logic_error_{token}"); end when;',
    ]
    patched = _inject_dynamic_block(model_text, decl_lines=decl, eq_lines=eq)
    objects = [{"kind": "event_threshold", "effect": "event_logic_error", "name": f"__gf_event_state_{token}"}]
    return patched, objects, "gateforge_event_logic_error"


def _mutate_semantic_drift_after_compile_pass(model_text: str, token: str) -> tuple[str, list[dict], str]:
    decl = [f"  Real __gf_sem_state_{token}(start=1.0);"]
    eq = [
        f"  der(__gf_sem_state_{token}) = -1.0 * __gf_sem_state_{token}; // gateforge_semantic_drift_after_compile_pass",
        f'  assert(__gf_sem_state_{token} < -1.0e-6, "gateforge_semantic_drift_after_compile_pass_{token}");',
    ]
    patched = _inject_dynamic_block(model_text, decl_lines=decl, eq_lines=eq)
    objects = [{"kind": "semantic_sign_flip", "effect": "semantic_drift_after_compile_pass", "name": f"__gf_sem_state_{token}"}]
    return patched, objects, "gateforge_semantic_drift_after_compile_pass"


def build_wave2_1_harder_dynamics_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
    exclude_models_path: str = "",
) -> dict:
    payload = load_wave2_1_harder_dynamics_manifest(manifest_path)
    libraries, manifest_reasons = validate_wave2_1_harder_dynamics_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    reasons = list(manifest_reasons)
    excluded_payload = _load_json(exclude_models_path) if str(exclude_models_path or "").strip() else {}
    excluded_qualified = {_norm(item).lower() for item in (excluded_payload.get("qualified_model_names") or []) if _norm(item)}
    excluded_model_ids = {_norm(item).lower() for item in (excluded_payload.get("model_ids") or []) if _norm(item)}
    selected_models: list[tuple[dict, dict]] = []
    excluded_models: list[dict] = []
    for library in libraries:
        for model in library.get("allowed_models") or []:
            if not isinstance(model, dict):
                continue
            model_id = _norm(model.get("model_id")).lower()
            qualified = _norm(model.get("qualified_model_name")).lower()
            if model_id in excluded_model_ids or qualified in excluded_qualified:
                excluded_models.append({"library_id": _norm(library.get("library_id")).lower(), "model_id": model_id, "qualified_model_name": _norm(model.get("qualified_model_name"))})
                continue
            selected_models.append((library, model))

    copied_source_paths: dict[str, str] = {}
    taskset_tasks: list[dict] = []
    records: list[dict] = []
    counts_by_failure: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_library: dict[str, int] = {}
    diagnostic_expectation_by_failure_type: dict[str, dict] = {}

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
        for item in model.get("component_hints") or []:
            _append_unique(component_hints, set(component_hints), item)
        connector_hints = _infer_connector_hints(connect_rows, [str(x) for x in (model.get("connector_hints") or []) if isinstance(x, str)])
        domain = _norm(library.get("domain")).lower()
        scale_hint = _norm(model.get("scale_hint") or library.get("scale_hint") or "small").lower()
        seen_risk_band = _norm(model.get("seen_risk_band") or library.get("seen_risk_band")).lower()
        source_type = _norm(model.get("source_type") or library.get("source_type")).lower()

        for failure_type in failure_types:
            meta = FAILURE_METADATA[failure_type]
            token = _slug(_sha256_text(f"{library_id}:{model_id}:{failure_type}")[:10]) or "dyn"
            if failure_type == "solver_sensitive_simulate_failure":
                mutated_text, mutated_objects, mutation_excerpt = _mutate_solver_sensitive_simulate_failure(source_text, token)
            elif failure_type == "event_logic_error":
                mutated_text, mutated_objects, mutation_excerpt = _mutate_event_logic_error(source_text, token)
            else:
                mutated_text, mutated_objects, mutation_excerpt = _mutate_semantic_drift_after_compile_pass(source_text, token)
            task_id = f"wave2_1_{library_id}_{model_id}_{failure_type}"
            mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
            _write_text(mutated_path, mutated_text)
            task = {
                "task_id": task_id,
                "scale": scale_hint,
                "failure_type": failure_type,
                "category": meta["category"],
                "dynamic_error_family": meta["dynamic_error_family"],
                "expected_stage": meta["expected_stage"],
                "expected_observed_error_type": meta["expected_observed_error_type"],
                "diagnostic_expectation": meta["diagnostic_expectation"],
                "mutation_operator": meta["mutation_operator"],
                "mutation_operator_family": meta["mutation_operator_family"],
                "mock_success_round": meta["mock_success_round"],
                "mock_round_duration_sec": 30,
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
            diagnostic_expectation_by_failure_type[failure_type] = {
                "expected_stage": meta["expected_stage"],
                "expected_observed_error_type": meta["expected_observed_error_type"],
                "dynamic_error_family": meta["dynamic_error_family"],
                "diagnostic_expectation": meta["diagnostic_expectation"],
            }
            records.append({"task_id": task_id, "status": "PASS", "failure_type": failure_type, "library_id": library_id, "model_id": model_id})

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
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_real_path,
        "failure_types": list(failure_types),
        "total_tasks": len(taskset_tasks),
        "library_count": len({_norm(task.get("source_library")) for task in taskset_tasks if _norm(task.get("source_library"))}),
        "model_count": len({_norm(task.get("model_hint")) for task in taskset_tasks if _norm(task.get("model_hint"))}),
        "counts_by_failure_type": counts_by_failure,
        "counts_by_library": counts_by_library,
        "diagnostic_expectation_by_failure_type": diagnostic_expectation_by_failure_type,
        "provenance_completeness_pct": _ratio(provenance_complete_count, len(taskset_tasks)),
        "library_hints_nonempty_pct": _ratio(len([task for task in taskset_tasks if task.get("library_hints")]), len(taskset_tasks)),
        "excluded_model_count": len(excluded_models),
        "excluded_models": excluded_models,
        "records": records,
        "reasons": sorted(set(reasons)),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
    }
    taskset_unfrozen = {"schema_version": SCHEMA_VERSION, "generated_at_utc": summary["generated_at_utc"], "tasks": taskset_tasks}
    taskset_frozen = dict(taskset_unfrozen)

    _write_json(out_root / "manifest.json", payload)
    _write_json(out_root / "summary.json", summary)
    _write_json(out_root / "taskset_unfrozen.json", taskset_unfrozen)
    _write_json(out_root / "taskset_frozen.json", taskset_frozen)
    _write_markdown(_default_md_path(str(out_root / "summary.json")), summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave2.1 harder-dynamics taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_wave2_1_harder_dynamics_taskset_v1")
    parser.add_argument("--failure-types", default="solver_sensitive_simulate_failure,event_logic_error,semantic_drift_after_compile_pass")
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_wave2_1_harder_dynamics_taskset_v1")
    parser.add_argument("--exclude-models-json", default="")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)
    summary = build_wave2_1_harder_dynamics_taskset(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed),
        exclude_models_path=str(args.exclude_models_json or ""),
    )
    print(json.dumps({"status": summary.get("status"), "total_tasks": summary.get("total_tasks"), "library_count": summary.get("library_count")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
