from __future__ import annotations

import argparse
import hashlib
import json
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
    _write_text,
)
from .agent_modelica_wave2_2_coupled_hard_taskset_v1 import (
    _difficulty_rejection_reasons,
    _extract_source_dependency_objects,
    _mutate_control_loop_sign_semantic_drift,
    _mutate_cross_component_parameter_coupling_error,
    _mutate_mode_switch_guard_logic_error,
    _pick_dependency_endpoints,
    _repair_triviality_risk,
)
from .agent_modelica_wave2_realism_taskset_v1 import (
    _mutate_array_dimension_mismatch,
    _mutate_overconstrained_system,
    _mutate_parameter_binding_error,
)
from .agent_modelica_wave2_1_harder_dynamics_taskset_v1 import (
    _mutate_event_logic_error,
    _mutate_semantic_drift_after_compile_pass,
    _mutate_solver_sensitive_simulate_failure,
)
from .agent_modelica_multi_round_failure_manifest_v1 import (
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_multi_round_failure_manifest,
    validate_multi_round_failure_manifest,
)


SCHEMA_VERSION = "agent_modelica_multi_round_failure_taskset_v1"
DEFAULT_FAILURE_TYPES = (
    "cascading_structural_failure",
    "coupled_conflict_failure",
    "false_friend_patch_trap",
)
FAILURE_METADATA = {
    "cascading_structural_failure": {
        "category": "multi_round_cascade",
        "multi_round_family": "cascade",
        "trap_kind": "second_layer_exposed_after_first_fix",
        "expected_stage": "simulate",
        "expected_stage_sequence": ["check", "simulate"],
        "expected_observed_error_type": "simulate_error",
        "diagnostic_expectation": "cascading_structural_failure",
        "mock_success_round": 3,
        "cascade_depth": 2,
    },
    "coupled_conflict_failure": {
        "category": "multi_round_conflict",
        "multi_round_family": "coupled_conflict",
        "trap_kind": "paired_conflict_requires_group_repair",
        "expected_stage": "simulate",
        "expected_stage_sequence": ["simulate", "simulate"],
        "expected_observed_error_type": "semantic_regression",
        "diagnostic_expectation": "coupled_conflict_failure",
        "mock_success_round": 2,
        "cascade_depth": 2,
    },
    "false_friend_patch_trap": {
        "category": "multi_round_false_friend",
        "multi_round_family": "false_friend",
        "trap_kind": "natural_local_patch_leads_to_second_failure",
        "expected_stage": "simulate",
        "expected_stage_sequence": ["simulate", "simulate"],
        "expected_observed_error_type": "semantic_regression",
        "diagnostic_expectation": "false_friend_patch_trap",
        "mock_success_round": 2,
        "cascade_depth": 2,
    },
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _variant_suffix(variant_tag: str) -> str:
    return _slug(_norm(variant_tag))


def _variant_index(variant_tag: str, *, failure_type: str, modulo: int) -> int:
    if modulo <= 0 or not _norm(variant_tag):
        return 0
    digest = _sha256_text(f"{failure_type}:{_norm(variant_tag)}")
    return int(digest[:8], 16) % modulo


def _rewrite_count(objects: list[dict]) -> int:
    count = 0
    for item in objects:
        if not isinstance(item, dict):
            continue
        kind = _norm(item.get("kind")).lower()
        if "rewrite" in kind:
            count += 1
    return count


def _apply_combo(
    source_text: str,
    *,
    token: str,
    connect_rows: list[dict],
    dependency_endpoints: list[str],
    mutator_names: list[str],
) -> tuple[str, list[dict], list[str], float]:
    current_text = source_text
    mutated_objects: list[dict] = []
    used_dependencies: list[str] = []
    failure_signal_delay_sec = 0.0
    for idx, name in enumerate(mutator_names):
        part_token = f"{token}{idx}"
        if name == "over":
            current_text, objects, _excerpt = _mutate_overconstrained_system(current_text, connect_rows)
            deps = []
            delay = 0.0
        elif name == "param":
            current_text, objects, _excerpt = _mutate_parameter_binding_error(current_text)
            deps = []
            delay = 0.0
        elif name == "array":
            current_text, objects, _excerpt = _mutate_array_dimension_mismatch(current_text)
            deps = []
            delay = 0.0
        elif name == "solver":
            current_text, objects, _excerpt = _mutate_solver_sensitive_simulate_failure(current_text, part_token)
            deps = []
            delay = 0.7
        elif name == "event":
            current_text, objects, _excerpt = _mutate_event_logic_error(current_text, part_token)
            deps = []
            delay = 0.6
        elif name == "sem":
            current_text, objects, _excerpt = _mutate_semantic_drift_after_compile_pass(current_text, part_token)
            deps = []
            delay = 0.8
        elif name == "cross":
            current_text, objects, _excerpt, deps, delay = _mutate_cross_component_parameter_coupling_error(current_text, part_token, dependency_endpoints)
        elif name == "control":
            current_text, objects, _excerpt, deps, delay = _mutate_control_loop_sign_semantic_drift(current_text, part_token, dependency_endpoints)
        else:
            current_text, objects, _excerpt, deps, delay = _mutate_mode_switch_guard_logic_error(current_text, part_token, dependency_endpoints)
        mutated_objects.extend(objects)
        for dep in deps:
            if dep not in used_dependencies:
                used_dependencies.append(dep)
        failure_signal_delay_sec = max(failure_signal_delay_sec, float(delay or 0.0))
    return current_text, mutated_objects, used_dependencies, failure_signal_delay_sec


def _select_combo(
    *,
    failure_type: str,
    source_text: str,
    token: str,
    connect_rows: list[dict],
    dependency_endpoints: list[str],
    variant_tag: str = "",
) -> tuple[str, list[dict], list[str], float]:
    combo_candidates = {
        "cascading_structural_failure": [["over", "solver", "cross"], ["over", "event", "guard"]],
        "coupled_conflict_failure": [["param", "cross", "control"], ["array", "cross", "guard"]],
        "false_friend_patch_trap": [["event", "control", "guard"], ["sem", "control", "cross"]],
    }[failure_type]
    if _norm(variant_tag):
        shift = _variant_index(variant_tag, failure_type=failure_type, modulo=len(combo_candidates))
        combo_candidates = combo_candidates[shift:] + combo_candidates[:shift]
    best: tuple[str, list[dict], list[str], float] | None = None
    best_score = (-1, -1)
    for combo in combo_candidates:
        patched, objects, deps, delay = _apply_combo(
            source_text,
            token=token,
            connect_rows=connect_rows,
            dependency_endpoints=dependency_endpoints,
            mutator_names=combo,
        )
        score = (_rewrite_count(objects), len(deps))
        if score > best_score:
            best = (patched, objects, deps, delay)
            best_score = score
        if score[0] >= 4 and score[1] >= 3:
            return patched, objects, deps, delay
    assert best is not None
    return best


def _multi_round_rejection_reasons(
    *,
    mutation_span_count: int,
    delayed_failure_signal: bool,
    source_dependency_count: int,
    uses_existing_equation_context: bool,
    failure_signal_delay_sec: float,
    source_rewrite_count: int,
) -> list[str]:
    reasons = _difficulty_rejection_reasons(
        mutation_span_count=mutation_span_count,
        delayed_failure_signal=delayed_failure_signal,
        source_dependency_count=source_dependency_count,
        uses_existing_equation_context=uses_existing_equation_context,
        failure_signal_delay_sec=failure_signal_delay_sec,
    )
    if source_rewrite_count < 4:
        reasons.append("source_rewrite_count_below_multi_round_minimum")
    return sorted(set(reasons))


def build_multi_round_failure_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
    exclude_task_ids_json: str | None = None,
    variant_tag: str = "",
    allow_partial_taskset: bool = False,
) -> dict:
    payload = load_multi_round_failure_manifest(manifest_path)
    libraries, manifest_reasons = validate_multi_round_failure_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    reasons = list(manifest_reasons)

    excluded_task_ids: set[str] = set()
    if exclude_task_ids_json:
        exclude_payload = _load_json(exclude_task_ids_json)
        for item in exclude_payload.get("task_ids") or []:
            normalized = _norm(item)
            if normalized:
                excluded_task_ids.add(normalized)

    selected_models: list[tuple[dict, dict]] = []
    for library in libraries:
        for model in library.get("allowed_models") or []:
            if isinstance(model, dict):
                selected_models.append((library, model))

    copied_source_paths: dict[str, str] = {}
    taskset_tasks: list[dict] = []
    rejected_candidates: list[dict] = []
    counts_by_failure: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_library: dict[str, int] = {}
    counts_by_multi_round_family: dict[str, int] = {}
    counts_by_expected_rounds_min: dict[str, int] = {}
    cascade_depth_distribution: dict[str, int] = {}
    rejection_reasons: dict[str, int] = {}

    for library, model in selected_models:
        model_path = Path(_norm(model.get("model_path")))
        source_text = model_path.read_text(encoding="utf-8", errors="ignore")
        connect_rows = _extract_connects(source_text)
        dependency_endpoints = _pick_dependency_endpoints(connect_rows, count=2)
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
            variant_suffix = _variant_suffix(variant_tag)
            token = _slug(_sha256_text(f"{library_id}:{model_id}:{failure_type}:{variant_suffix}")[:10]) or "mrf"
            mutated_text, mutated_objects, used_dependencies, failure_signal_delay_sec = _select_combo(
                failure_type=failure_type,
                source_text=source_text,
                token=token,
                connect_rows=connect_rows,
                dependency_endpoints=dependency_endpoints,
                variant_tag=variant_suffix,
            )
            task_id = f"multi_round_{library_id}_{model_id}_{failure_type}"
            if variant_suffix:
                task_id = f"{task_id}_{variant_suffix}"
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
            filename = f"{library_id}_{model_id}_{failure_type}"
            if variant_suffix:
                filename = f"{filename}_{variant_suffix}"
            mutated_path = mutants_dir / failure_type / f"{filename}.mo"
            _write_text(mutated_path, mutated_text)
            mutation_span_count = len(mutated_objects)
            source_rewrite_count = _rewrite_count(mutated_objects)
            delayed_failure_signal = True
            source_dependency_objects = _extract_source_dependency_objects(connect_rows)
            for dep in used_dependencies:
                if dep not in source_dependency_objects:
                    source_dependency_objects.append(dep)
            source_dependency_count = len([item for item in used_dependencies if _norm(item)])
            uses_existing_equation_context = source_dependency_count >= 3
            repair_triviality_risk = _repair_triviality_risk(
                mutation_span_count=mutation_span_count,
                delayed_failure_signal=delayed_failure_signal,
                source_dependency_count=source_dependency_count,
                uses_existing_equation_context=uses_existing_equation_context,
                failure_signal_delay_sec=failure_signal_delay_sec,
            )
            task_rejection_reasons = _multi_round_rejection_reasons(
                mutation_span_count=mutation_span_count,
                delayed_failure_signal=delayed_failure_signal,
                source_dependency_count=source_dependency_count,
                uses_existing_equation_context=uses_existing_equation_context,
                failure_signal_delay_sec=failure_signal_delay_sec,
                source_rewrite_count=source_rewrite_count,
            )
            if task_rejection_reasons:
                rejected_candidates.append(
                    {
                        "task_id": task_id,
                        "failure_type": failure_type,
                        "library_id": library_id,
                        "model_id": model_id,
                        "source_rewrite_count": source_rewrite_count,
                        "mutation_span_count": mutation_span_count,
                        "source_dependency_count": source_dependency_count,
                        "failure_signal_delay_sec": failure_signal_delay_sec,
                        "rejection_reasons": task_rejection_reasons,
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
                "multi_round_family": meta["multi_round_family"],
                "trap_kind": meta["trap_kind"],
                "expected_rounds_min": 2,
                "expected_stage": meta["expected_stage"],
                "expected_stage_sequence": list(meta["expected_stage_sequence"]),
                "expected_observed_error_type": meta["expected_observed_error_type"],
                "diagnostic_expectation": meta["diagnostic_expectation"],
                "mock_success_round": meta["mock_success_round"],
                "mock_round_duration_sec": 30,
                "cascade_depth": meta["cascade_depth"],
                "repair_triviality_risk": repair_triviality_risk,
                "mutation_span_count": mutation_span_count,
                "source_rewrite_count": source_rewrite_count,
                "delayed_failure_signal": delayed_failure_signal,
                "compile_pass_expected": True,
                "simulate_phase_required": True,
                "trivial_restore_guard": bool(mutation_span_count >= 6 and source_rewrite_count >= 4 and source_dependency_count >= 3),
                "source_dependency_count": source_dependency_count,
                "uses_existing_equation_context": uses_existing_equation_context,
                "failure_signal_delay_sec": failure_signal_delay_sec,
                "source_dependency_objects": source_dependency_objects,
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
                "mutation_excerpt": f"gateforge_{failure_type}",
                "seen_risk_band": seen_risk_band,
                "source_type": source_type,
            }
            taskset_tasks.append(task)
            counts_by_failure[failure_type] = int(counts_by_failure.get(failure_type, 0)) + 1
            counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1
            counts_by_multi_round_family[meta["multi_round_family"]] = int(counts_by_multi_round_family.get(meta["multi_round_family"], 0)) + 1
            counts_by_expected_rounds_min["2"] = int(counts_by_expected_rounds_min.get("2", 0)) + 1
            cascade_depth_distribution[str(meta["cascade_depth"])] = int(cascade_depth_distribution.get(str(meta["cascade_depth"]), 0)) + 1

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
        "variant_tag": _norm(variant_tag),
        "mode": "multi_round_failure_frozen",
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_real_path,
        "failure_types": list(failure_types),
        "total_tasks": len(taskset_tasks),
        "library_count": len({str(task.get('source_library') or '').strip() for task in taskset_tasks if str(task.get('source_library') or '').strip()}),
        "model_count": len(selected_models),
        "counts_by_library": counts_by_library,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_multi_round_family": counts_by_multi_round_family,
        "counts_by_expected_rounds_min": counts_by_expected_rounds_min,
        "cascade_depth_distribution": cascade_depth_distribution,
        "provenance_completeness_pct": _ratio(provenance_complete_count, len(taskset_tasks)),
        "library_hints_nonempty_pct": _ratio(len([task for task in taskset_tasks if task.get("library_hints")]), len(taskset_tasks)),
        "rejected_candidate_count": len(rejected_candidates),
        "rejection_reasons": rejection_reasons,
        "taskset_unfrozen_path": str((out_root / "taskset_unfrozen.json").resolve()),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
        "task_construction_rejections_path": str((out_root / "task_construction_rejections.json").resolve()),
        "reasons": sorted(set(reasons)),
        "allow_partial_taskset": bool(allow_partial_taskset),
    }
    frozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "multi_round_failure_frozen", "tasks": taskset_tasks}
    unfrozen_payload = {"schema_version": SCHEMA_VERSION, "mode": "multi_round_failure_unfrozen", "tasks": taskset_tasks}
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
    markdown = [
        "# Multi-Round Failure Taskset",
        "",
        f"- status: `{status}`",
        f"- total_tasks: `{len(taskset_tasks)}`",
        f"- counts_by_failure_type: `{json.dumps(counts_by_failure, sort_keys=True)}`",
        f"- counts_by_multi_round_family: `{json.dumps(counts_by_multi_round_family, sort_keys=True)}`",
    ]
    Path(_default_md_path(str((out_root / "summary.json").resolve()))).write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "total_tasks": len(taskset_tasks), "counts_by_failure_type": counts_by_failure}))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-round failure frozen taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_multi_round_failure_taskset_v1")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_multi_round_failure_taskset_v1")
    parser.add_argument("--exclude-task-ids-json")
    parser.add_argument("--variant-tag", default="")
    parser.add_argument("--allow-partial-taskset", action="store_true")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    summary = build_multi_round_failure_taskset(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed),
        exclude_task_ids_json=str(args.exclude_task_ids_json) if args.exclude_task_ids_json else None,
        variant_tag=str(args.variant_tag or ""),
        allow_partial_taskset=bool(args.allow_partial_taskset),
    )
    if summary.get("status") != "PASS" and not bool(args.allow_partial_taskset):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
