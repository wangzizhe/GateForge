from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_wave2_realism_manifest_v1 import (
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_wave2_realism_manifest,
    validate_wave2_realism_manifest,
)
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
    _sha256,
    _slug,
    _task_provenance_complete,
    _write_json,
    _write_markdown,
    _write_text,
)


SCHEMA_VERSION = "agent_modelica_wave2_realism_taskset_v1"
DEFAULT_FAILURE_TYPES = ("overconstrained_system", "parameter_binding_error", "array_dimension_mismatch")
FAILURE_METADATA = {
    "overconstrained_system": {
        "category": "constraint_structure",
        "expected_stage": "check",
        "expected_observed_error_type": "constraint_violation",
        "mutation_operator": "inject_duplicate_equation",
        "mutation_operator_family": "wave2_structural_realism",
        "mock_success_round": 2,
    },
    "parameter_binding_error": {
        "category": "parameterization",
        "expected_stage": "check",
        "expected_observed_error_type": "model_check_error",
        "mutation_operator": "replace_parameter_binding_with_invalid_literal",
        "mutation_operator_family": "wave2_parameter_realism",
        "mock_success_round": 2,
    },
    "array_dimension_mismatch": {
        "category": "array_shape",
        "expected_stage": "check",
        "expected_observed_error_type": "model_check_error",
        "mutation_operator": "inject_array_binding_dimension_mismatch",
        "mutation_operator_family": "wave2_array_realism",
        "mock_success_round": 2,
    },
}
PARAM_ASSIGN_RE = re.compile(r"(?P<prefix>\([^\n;]*?\b)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>[^,\)\n;]+)")


def _insert_after_equation(lines: list[str], injected_line: str) -> list[str]:
    out = list(lines)
    for idx, line in enumerate(out):
        if re.match(r"^\s*equation\s*$", line):
            out.insert(idx + 1, injected_line)
            return out
    for idx, line in enumerate(out):
        if re.match(r"^\s*end\s+[A-Za-z_][A-Za-z0-9_]*\s*;\s*$", line):
            out.insert(idx, "equation")
            out.insert(idx + 1, injected_line)
            return out
    out.append("equation")
    out.append(injected_line)
    return out


def _insert_before_equation(lines: list[str], injected_line: str) -> list[str]:
    out = list(lines)
    for idx, line in enumerate(out):
        if re.match(r"^\s*equation\s*$", line):
            out.insert(idx, injected_line)
            return out
    for idx, line in enumerate(out):
        if re.match(r"^\s*end\s+[A-Za-z_][A-Za-z0-9_]*\s*;\s*$", line):
            out.insert(idx, injected_line)
            return out
    out.append(injected_line)
    return out


def _mutate_overconstrained_system(model_text: str, connect_rows: list[dict]) -> tuple[str, list[dict], str]:
    row = connect_rows[0]
    injected = f"  {row['lhs']} = {row['rhs']}; // gateforge_overconstrained_system"
    patched = "\n".join(_insert_after_equation(model_text.splitlines(), injected)) + "\n"
    objects = [{"kind": "duplicate_equation", "effect": "overconstrained_system", "lhs": row["lhs"], "rhs": row["rhs"]}]
    return patched, objects, injected


def _mutate_parameter_binding_error(model_text: str) -> tuple[str, list[dict], str]:
    match = PARAM_ASSIGN_RE.search(model_text)
    if not match:
        injected = "  parameter Real gateforge_wave2_bad_parameter = \"bad\"; // gateforge_parameter_binding_error"
        patched = "\n".join(_insert_before_equation(model_text.splitlines(), injected)) + "\n"
        objects = [{"kind": "parameter_binding", "effect": "parameter_binding_error", "binding": "gateforge_wave2_bad_parameter"}]
        return patched, objects, injected
    replacement = f"{match.group('prefix')}{match.group('name')} = \"gateforge_bad_binding\" /* gateforge_parameter_binding_error */"
    patched = model_text[: match.start()] + replacement + model_text[match.end() :]
    objects = [{"kind": "parameter_binding", "effect": "parameter_binding_error", "binding": match.group("name")}]
    return patched, objects, match.group(0)


def _mutate_array_dimension_mismatch(model_text: str) -> tuple[str, list[dict], str]:
    injected = "  Real gateforge_array_dimension_probe[2] = {1}; // gateforge_array_dimension_mismatch"
    patched = "\n".join(_insert_before_equation(model_text.splitlines(), injected)) + "\n"
    objects = [{"kind": "array_binding", "effect": "array_dimension_mismatch", "name": "gateforge_array_dimension_probe"}]
    return patched, objects, injected


def build_wave2_realism_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
    exclude_models_path: str = "",
) -> dict:
    payload = load_wave2_realism_manifest(manifest_path)
    libraries, manifest_reasons = validate_wave2_realism_manifest(payload)
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
    counts_by_error_family: dict[str, int] = {}
    counts_by_category: dict[str, int] = {}
    counts_by_library: dict[str, int] = {}
    counts_by_seen_risk_band: dict[str, int] = {}
    diagnostic_expectation_by_failure_type: dict[str, dict] = {}

    for library, model in selected_models:
        model_path = Path(_norm(model.get("model_path")))
        source_text = model_path.read_text(encoding="utf-8", errors="ignore")
        connect_rows = _extract_connects(source_text)
        if not connect_rows:
            reasons.append(f"connect_statement_missing:{_norm(library.get('library_id'))}:{_norm(model.get('model_id'))}")
            continue
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
        for item in library.get("library_hints") or []:
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
            if failure_type == "overconstrained_system":
                mutated_text, mutated_objects, mutation_excerpt = _mutate_overconstrained_system(source_text, connect_rows)
            elif failure_type == "parameter_binding_error":
                mutated_text, mutated_objects, mutation_excerpt = _mutate_parameter_binding_error(source_text)
            else:
                mutated_text, mutated_objects, mutation_excerpt = _mutate_array_dimension_mismatch(source_text)
            task_id = f"wave2_{library_id}_{model_id}_{failure_type}"
            mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
            _write_text(mutated_path, mutated_text)
            task = {
                "task_id": task_id,
                "scale": scale_hint,
                "failure_type": failure_type,
                "category": meta["category"],
                "error_family": meta["expected_observed_error_type"],
                "expected_stage": meta["expected_stage"],
                "expected_observed_error_type": meta["expected_observed_error_type"],
                "mutation_operator": meta["mutation_operator"],
                "mutation_operator_family": meta["mutation_operator_family"],
                "mock_success_round": meta["mock_success_round"],
                "mock_round_duration_sec": 20 if scale_hint == "small" else 30,
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
            counts_by_error_family[meta["expected_observed_error_type"]] = int(counts_by_error_family.get(meta["expected_observed_error_type"], 0)) + 1
            counts_by_category[meta["category"]] = int(counts_by_category.get(meta["category"], 0)) + 1
            counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1
            counts_by_seen_risk_band[seen_risk_band] = int(counts_by_seen_risk_band.get(seen_risk_band, 0)) + 1
            diagnostic_expectation_by_failure_type[failure_type] = {
                "expected_stage": meta["expected_stage"],
                "expected_observed_error_type": meta["expected_observed_error_type"],
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
        reasons.append("task_count_below_target")
        status = "FAIL"
    return {
        "status": status,
        "reasons": sorted(set(reasons)),
        "libraries": libraries,
        "tasks": taskset_tasks,
        "records": records,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_error_family": counts_by_error_family,
        "counts_by_category": counts_by_category,
        "counts_by_library": counts_by_library,
        "counts_by_seen_risk_band": counts_by_seen_risk_band,
        "diagnostic_expectation_by_failure_type": diagnostic_expectation_by_failure_type,
        "library_count": len({_norm(library.get('library_id')).lower() for library, _ in selected_models}),
        "model_count": len(selected_models),
        "provenance_completeness_pct": _ratio(provenance_complete_count, len(taskset_tasks)),
        "source_models_dir": str(source_models_dir.resolve()),
        "mutants_dir": str(mutants_dir.resolve()),
        "manifest_path": manifest_real_path,
        "exclude_models_path": str(exclude_models_path or ""),
        "excluded_model_count": len(excluded_models),
        "excluded_models": excluded_models,
        "holdout_ratio": holdout_ratio,
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave2 realism frozen taskset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_wave2_realism_taskset_v1")
    parser.add_argument("--failure-types", default="overconstrained_system,parameter_binding_error,array_dimension_mismatch")
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_wave2_realism_taskset_v1")
    parser.add_argument("--exclude-models-json", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)
    built = build_wave2_realism_taskset(
        manifest_path=str(args.manifest),
        out_dir=str(args.out_dir),
        failure_types=failure_types,
        holdout_ratio=float(args.holdout_ratio),
        seed=str(args.seed),
        exclude_models_path=str(args.exclude_models_json),
    )
    out_root = Path(args.out_dir)
    taskset_unfrozen_path = out_root / "taskset_unfrozen.json"
    taskset_frozen_path = out_root / "taskset_frozen.json"
    manifest_out_path = out_root / "manifest.json"
    sha_path = out_root / "sha256.json"
    summary_path = Path(args.out or (out_root / "summary.json"))
    tasks = [dict(task) for task in (built.get("tasks") or []) if isinstance(task, dict)]
    taskset_unfrozen = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "wave2_realism_unfrozen",
        "tasks": [{k: v for k, v in task.items() if k != "split"} for task in tasks],
        "sources": {"manifest": built.get("manifest_path")},
    }
    taskset_frozen = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "wave2_realism_frozen",
        "tasks": tasks,
        "sources": {"manifest": built.get("manifest_path")},
    }
    _write_json(taskset_unfrozen_path, taskset_unfrozen)
    _write_json(taskset_frozen_path, taskset_frozen)
    manifest_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": built.get("status"),
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": built.get("manifest_path"),
        "failure_types": failure_types,
        "library_count": built.get("library_count"),
        "model_count": built.get("model_count"),
        "total_tasks": len(tasks),
        "counts_by_failure_type": built.get("counts_by_failure_type"),
        "counts_by_error_family": built.get("counts_by_error_family"),
        "counts_by_library": built.get("counts_by_library"),
        "counts_by_seen_risk_band": built.get("counts_by_seen_risk_band"),
        "diagnostic_expectation_by_failure_type": built.get("diagnostic_expectation_by_failure_type"),
        "provenance_completeness_pct": built.get("provenance_completeness_pct"),
        "exclude_models_path": built.get("exclude_models_path"),
        "excluded_model_count": built.get("excluded_model_count"),
        "excluded_models": built.get("excluded_models"),
        "builder_provenance": {"builder_source_path": str(Path(__file__).resolve()), "builder_source_sha": _sha256(Path(__file__).resolve())},
        "files": {"taskset_unfrozen": str(taskset_unfrozen_path), "taskset_frozen": str(taskset_frozen_path)},
        "libraries": built.get("libraries"),
        "reasons": built.get("reasons"),
    }
    _write_json(manifest_out_path, manifest_payload)
    _write_json(
        sha_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "taskset_unfrozen": _sha256(taskset_unfrozen_path),
            "taskset_frozen": _sha256(taskset_frozen_path),
            "manifest": _sha256(manifest_out_path),
        },
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": built.get("status"),
        "total_tasks": len(tasks),
        "library_count": built.get("library_count"),
        "model_count": built.get("model_count"),
        "counts_by_failure_type": built.get("counts_by_failure_type"),
        "counts_by_error_family": built.get("counts_by_error_family"),
        "counts_by_library": built.get("counts_by_library"),
        "counts_by_seen_risk_band": built.get("counts_by_seen_risk_band"),
        "diagnostic_expectation_by_failure_type": built.get("diagnostic_expectation_by_failure_type"),
        "provenance_completeness_pct": built.get("provenance_completeness_pct"),
        "taskset_unfrozen_path": str(taskset_unfrozen_path),
        "taskset_frozen_path": str(taskset_frozen_path),
        "manifest_path": str(manifest_out_path),
        "reasons": built.get("reasons"),
        "records": built.get("records"),
    }
    _write_json(summary_path, summary)
    _write_markdown(str(args.report_out or _default_md_path(str(summary_path))), summary)
    print(json.dumps({"status": summary.get("status"), "total_tasks": len(tasks), "library_count": built.get("library_count")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
