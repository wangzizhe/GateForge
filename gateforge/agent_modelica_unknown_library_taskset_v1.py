from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_unknown_library_manifest_v1 import (
    SCHEMA_VERSION as MANIFEST_SCHEMA_VERSION,
    load_unknown_library_manifest,
    validate_unknown_library_manifest,
)


SCHEMA_VERSION = "agent_modelica_unknown_library_taskset_v1"
DEFAULT_FAILURE_TYPES = ("underconstrained_system", "connector_mismatch", "initialization_infeasible")
FAILURE_METADATA = {
    "underconstrained_system": {
        "category": "topology_wiring",
        "expected_stage": "check",
        "mutation_operator": "remove_connect_statement",
        "mutation_operator_family": "topology_realism",
        "mock_success_round": 2,
    },
    "connector_mismatch": {
        "category": "topology_wiring",
        "expected_stage": "check",
        "mutation_operator": "replace_connector_endpoint",
        "mutation_operator_family": "topology_realism",
        "mock_success_round": 2,
    },
    "initialization_infeasible": {
        "category": "initialization",
        "expected_stage": "simulate",
        "mutation_operator": "inject_conflicting_initial_equation",
        "mutation_operator_family": "initialization_realism",
        "mock_success_round": 2,
    },
}
CONNECT_LINE_RE = re.compile(r"(?m)^(?P<indent>\s*)connect\s*\(\s*(?P<lhs>[^,]+?)\s*,\s*(?P<rhs>[^)]+?)\s*\).*?$")
DECLARATION_RE = re.compile(r"(?m)^\s*([A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)+)\s+([A-Za-z_][A-Za-z0-9_]*)")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: str) -> dict:
    p = Path(str(path or "").strip())
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Unknown Library Taskset v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- library_count: `{payload.get('library_count')}`",
        f"- model_count: `{payload.get('model_count')}`",
        f"- provenance_completeness_pct: `{payload.get('provenance_completeness_pct')}`",
        f"- library_hints_nonempty_pct: `{payload.get('library_hints_nonempty_pct')}`",
        "",
    ]
    for key, value in sorted((payload.get("counts_by_library") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _norm(value: object) -> str:
    return str(value or "").strip()


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", _norm(value).lower()).strip("_")
    return text or "item"


def _package_prefixes(package_name: str) -> list[str]:
    parts = [part.strip().lower() for part in str(package_name or "").split(".") if part.strip()]
    return [".".join(parts[:idx]) for idx in range(1, len(parts) + 1)]


def _append_unique(out: list[str], seen: set[str], value: object) -> None:
    text = _norm(value).lower()
    if text and text not in seen:
        out.append(text)
        seen.add(text)


def _extract_connects(model_text: str) -> list[dict]:
    rows: list[dict] = []
    for match in CONNECT_LINE_RE.finditer(model_text):
        lhs = _norm(match.group("lhs"))
        rhs = _norm(match.group("rhs"))
        rows.append(
            {
                "lhs": lhs,
                "rhs": rhs,
                "start": match.start(),
                "end": match.end(),
                "line": match.group(0),
                "indent": match.group("indent"),
            }
        )
    return rows


def _copy_source_model(source_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(source_path), str(dest_path))


def _insert_initial_equation(model_text: str, equation_line: str) -> str:
    lines = model_text.splitlines()
    if not lines:
        return model_text
    for idx, line in enumerate(lines):
        if re.match(r"^\s*initial\s+equation\s*$", line):
            lines.insert(idx + 1, equation_line)
            return "\n".join(lines) + "\n"
    for idx, line in enumerate(lines):
        if re.match(r"^\s*equation\s*$", line):
            lines.insert(idx, "initial equation")
            lines.insert(idx + 1, equation_line)
            return "\n".join(lines) + "\n"
    for idx, line in enumerate(lines):
        if re.match(r"^\s*end\s+[A-Za-z_][A-Za-z0-9_]*\s*;\s*$", line):
            lines.insert(idx, "initial equation")
            lines.insert(idx + 1, equation_line)
            return "\n".join(lines) + "\n"
    return model_text


def _mutate_underconstrained(model_text: str, connect_rows: list[dict]) -> tuple[str, list[dict], str]:
    row = connect_rows[0]
    replacement = f"{row['indent']}// gateforge_removed_connect({row['lhs']}, {row['rhs']});"
    patched = model_text[: row["start"]] + replacement + model_text[row["end"] :]
    objects = [
        {
            "kind": "connection_removed",
            "from": row["lhs"],
            "to": row["rhs"],
            "effect": "underconstrained_system",
        }
    ]
    return patched, objects, row["line"]


def _mutate_connector_mismatch(model_text: str, connect_rows: list[dict]) -> tuple[str, list[dict], str]:
    row = connect_rows[0]
    rhs = row["rhs"]
    if "." in rhs:
        head, _tail = rhs.split(".", 1)
        new_rhs = f"{head}.badPort"
    else:
        new_rhs = f"{rhs}_bad"
    replacement = f"{row['indent']}connect({row['lhs']}, {new_rhs});"
    patched = model_text[: row["start"]] + replacement + model_text[row["end"] :]
    objects = [
        {
            "kind": "connection_endpoint",
            "from": row["lhs"],
            "to_before": rhs,
            "to_after": new_rhs,
            "effect": "connector_mismatch",
        }
    ]
    return patched, objects, row["line"]


def _mutate_initialization_infeasible(model_text: str) -> tuple[str, list[dict], str]:
    line = "  0 = 1; // gateforge_initialization_infeasible"
    patched = _insert_initial_equation(model_text, line)
    objects = [{"kind": "initial_equation", "effect": "initialization_infeasible", "name": "0=1"}]
    return patched, objects, line


def _infer_component_hints(model_text: str, qualified_model_name: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in str(qualified_model_name).split("."):
        _append_unique(out, seen, part)
    for match in DECLARATION_RE.finditer(model_text):
        comp_type = _norm(match.group(1))
        comp_name = _norm(match.group(2))
        _append_unique(out, seen, comp_type)
        if "." in comp_type:
            _append_unique(out, seen, comp_type.rsplit(".", 1)[-1])
        _append_unique(out, seen, comp_name)
    return out


def _infer_connector_hints(connect_rows: list[dict], manifest_connectors: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in connect_rows:
        for endpoint in (row["lhs"], row["rhs"]):
            _append_unique(out, seen, endpoint)
            if "." in endpoint:
                _append_unique(out, seen, endpoint.split(".", 1)[1])
    for item in manifest_connectors:
        _append_unique(out, seen, item)
    return out


def _build_source_meta(manifest_path: str, library: dict, model: dict) -> dict:
    meta = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_path": manifest_path,
        "library_id": _norm(library.get("library_id")).lower(),
        "package_name": _norm(library.get("package_name")),
        "source_library": _norm(library.get("source_library")),
        "license_provenance": _norm(library.get("license_provenance")),
        "local_path": _norm(library.get("local_path")),
        "accepted_source_path": _norm(library.get("accepted_source_path")),
        "domain": _norm(library.get("domain")).lower(),
        "scale_hint": _norm(model.get("scale_hint") or library.get("scale_hint") or "small").lower(),
        "model_id": _norm(model.get("model_id")).lower(),
        "qualified_model_name": _norm(model.get("qualified_model_name")),
        "model_path": _norm(model.get("model_path")),
    }
    extra = library.get("source_meta") if isinstance(library.get("source_meta"), dict) else {}
    for key, value in extra.items():
        if key not in meta and value is not None:
            meta[key] = value
    return meta


def _task_provenance_complete(task: dict) -> bool:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    required = (
        "library_id",
        "package_name",
        "source_library",
        "license_provenance",
        "domain",
        "qualified_model_name",
    )
    if any(not _norm(source_meta.get(key)) for key in required):
        return False
    if not _norm(source_meta.get("local_path")) and not _norm(source_meta.get("accepted_source_path")):
        return False
    return True


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _assign_split(task: dict, holdout_ratio: float, seed: str) -> str:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    raw = "|".join(
        [
            seed,
            _norm(task.get("task_id")).lower(),
            _norm(task.get("failure_type")).lower(),
            _norm(task.get("scale")).lower(),
            _norm(source_meta.get("library_id")).lower(),
            _norm(source_meta.get("model_id")).lower(),
            _norm(source_meta.get("qualified_model_name")).lower(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10000
    threshold = int(max(0.0, min(1.0, float(holdout_ratio))) * 10000)
    return "holdout" if bucket < threshold else "train"


def build_unknown_library_taskset(
    *,
    manifest_path: str,
    out_dir: str,
    failure_types: list[str],
    holdout_ratio: float,
    seed: str,
    exclude_models_path: str = "",
) -> dict:
    payload = load_unknown_library_manifest(manifest_path)
    libraries, manifest_reasons = validate_unknown_library_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    out_root = Path(out_dir)
    source_models_dir = out_root / "source_models"
    mutants_dir = out_root / "mutants"
    selected_models: list[tuple[dict, dict]] = []
    reasons = list(manifest_reasons)
    excluded_payload = _load_json(exclude_models_path) if str(exclude_models_path or "").strip() else {}
    excluded_qualified = {
        _norm(item).lower()
        for item in (excluded_payload.get("qualified_model_names") or [])
        if _norm(item)
    }
    excluded_model_ids = {
        _norm(item).lower()
        for item in (excluded_payload.get("model_ids") or [])
        if _norm(item)
    }
    excluded_library_ids = {
        _norm(item).lower()
        for item in (excluded_payload.get("library_ids") or [])
        if _norm(item)
    }
    excluded_models: list[dict] = []

    for library in libraries:
        for model in library.get("allowed_models") or []:
            if isinstance(model, dict):
                library_id = _norm(library.get("library_id")).lower()
                model_id = _norm(model.get("model_id")).lower()
                qualified = _norm(model.get("qualified_model_name")).lower()
                if (
                    library_id in excluded_library_ids
                    or model_id in excluded_model_ids
                    or qualified in excluded_qualified
                ):
                    excluded_models.append(
                        {
                            "library_id": library_id,
                            "model_id": model_id,
                            "qualified_model_name": _norm(model.get("qualified_model_name")),
                        }
                    )
                    continue
                selected_models.append((library, model))

    taskset_tasks: list[dict] = []
    records: list[dict] = []
    counts_by_failure: dict[str, int] = {failure_type: 0 for failure_type in failure_types}
    counts_by_category: dict[str, int] = {}
    counts_by_library: dict[str, int] = {}
    copied_source_paths: dict[str, str] = {}

    for library, model in selected_models:
        model_path = Path(_norm(model.get("model_path")))
        if not model_path.exists():
            reasons.append(f"model_path_missing:{_norm(library.get('library_id'))}:{_norm(model.get('model_id'))}")
            continue
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

        for failure_type in failure_types:
            meta = FAILURE_METADATA[failure_type]
            if failure_type == "underconstrained_system":
                mutated_text, mutated_objects, mutation_excerpt = _mutate_underconstrained(source_text, connect_rows)
            elif failure_type == "connector_mismatch":
                mutated_text, mutated_objects, mutation_excerpt = _mutate_connector_mismatch(source_text, connect_rows)
            else:
                mutated_text, mutated_objects, mutation_excerpt = _mutate_initialization_infeasible(source_text)

            task_id = f"unknownlib_{library_id}_{model_id}_{failure_type}"
            mutated_path = mutants_dir / failure_type / f"{library_id}_{model_id}_{failure_type}.mo"
            _write_text(mutated_path, mutated_text)
            task = {
                "task_id": task_id,
                "scale": scale_hint,
                "failure_type": failure_type,
                "category": meta["category"],
                "expected_stage": meta["expected_stage"],
                "mutation_operator": meta["mutation_operator"],
                "mutation_operator_family": meta["mutation_operator_family"],
                "mock_success_round": meta["mock_success_round"],
                "mock_round_duration_sec": 15 if scale_hint == "small" else 25,
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
            }
            taskset_tasks.append(task)
            counts_by_failure[failure_type] = int(counts_by_failure.get(failure_type, 0)) + 1
            counts_by_category[meta["category"]] = int(counts_by_category.get(meta["category"], 0)) + 1
            counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1
            records.append(
                {
                    "task_id": task_id,
                    "status": "PASS",
                    "failure_type": failure_type,
                    "library_id": library_id,
                    "model_id": model_id,
                    "source_model_path": task["source_model_path"],
                    "mutated_model_path": task["mutated_model_path"],
                }
            )

    taskset_tasks = sorted(taskset_tasks, key=lambda row: (_norm(row.get("task_id")), _norm(row.get("mutated_model_path"))))
    for task in taskset_tasks:
        task["split"] = _assign_split(task, holdout_ratio=holdout_ratio, seed=seed)
    if taskset_tasks and not any(_norm(task.get("split")) == "holdout" for task in taskset_tasks):
        taskset_tasks[0]["split"] = "holdout"

    provenance_complete_count = len([task for task in taskset_tasks if _task_provenance_complete(task)])
    library_hints_nonempty_count = len([task for task in taskset_tasks if task.get("library_hints")])
    counts_by_scale: dict[str, int] = {}
    split_counts = {"train": 0, "holdout": 0}
    for task in taskset_tasks:
        scale = _norm(task.get("scale")).lower()
        split = _norm(task.get("split")).lower()
        counts_by_scale[scale] = int(counts_by_scale.get(scale, 0)) + 1
        if split in split_counts:
            split_counts[split] += 1

    hard_reasons = list(reasons)
    if len(taskset_tasks) < 12:
        if excluded_models:
            reasons.append("task_count_below_target_after_exclusions")
        else:
            reasons.append("task_count_below_target")
            hard_reasons.append("task_count_below_target")

    status = "PASS" if taskset_tasks and not hard_reasons else "FAIL"
    return {
        "status": status,
        "reasons": sorted(set(reasons)),
        "libraries": libraries,
        "tasks": taskset_tasks,
        "records": records,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_category": counts_by_category,
        "counts_by_scale": counts_by_scale,
        "counts_by_library": counts_by_library,
        "split_counts": split_counts,
        "library_count": len(libraries),
        "model_count": len(selected_models),
        "provenance_completeness_pct": _ratio(provenance_complete_count, len(taskset_tasks)),
        "library_hints_nonempty_pct": _ratio(library_hints_nonempty_count, len(taskset_tasks)),
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
    parser = argparse.ArgumentParser(description="Build unknown-library frozen taskset from curated private manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_unknown_library_taskset_v1")
    parser.add_argument("--failure-types", default="underconstrained_system,connector_mismatch,initialization_infeasible")
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--seed", default="agent_modelica_unknown_library_taskset_v1")
    parser.add_argument("--exclude-models-json", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)

    built = build_unknown_library_taskset(
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
        "mode": "unknown_library_unfrozen",
        "tasks": [{k: v for k, v in task.items() if k != "split"} for task in tasks],
        "sources": {"manifest": built.get("manifest_path")},
    }
    taskset_frozen = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "unknown_library_frozen",
        "tasks": tasks,
        "sources": {"manifest": built.get("manifest_path")},
        "split_freeze": {
            "schema_version": "agent_modelica_taskset_split_freeze_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "seed": built.get("seed"),
            "holdout_ratio": built.get("holdout_ratio"),
        },
    }
    _write_json(taskset_unfrozen_path, taskset_unfrozen)
    _write_json(taskset_frozen_path, taskset_frozen)

    builder_source_path = Path(__file__).resolve()
    manifest_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": built.get("status"),
        "manifest_path": built.get("manifest_path"),
        "failure_types": failure_types,
        "library_count": built.get("library_count"),
        "model_count": built.get("model_count"),
        "total_tasks": len(tasks),
        "counts_by_library": built.get("counts_by_library"),
        "counts_by_failure_type": built.get("counts_by_failure_type"),
        "counts_by_category": built.get("counts_by_category"),
        "counts_by_scale": built.get("counts_by_scale"),
        "split_counts": built.get("split_counts"),
        "provenance_completeness_pct": built.get("provenance_completeness_pct"),
        "library_hints_nonempty_pct": built.get("library_hints_nonempty_pct"),
        "builder_provenance": {
            "builder_source_path": str(builder_source_path),
            "builder_source_sha": _sha256(builder_source_path),
        },
        "exclude_models_path": built.get("exclude_models_path"),
        "excluded_model_count": built.get("excluded_model_count"),
        "excluded_models": built.get("excluded_models"),
        "files": {
            "taskset_unfrozen": str(taskset_unfrozen_path),
            "taskset_frozen": str(taskset_frozen_path),
            "source_models_dir": built.get("source_models_dir"),
            "mutants_dir": built.get("mutants_dir"),
        },
        "libraries": built.get("libraries"),
        "reasons": built.get("reasons"),
    }
    _write_json(manifest_out_path, manifest_payload)
    sha_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "taskset_unfrozen": _sha256(taskset_unfrozen_path),
        "taskset_frozen": _sha256(taskset_frozen_path),
        "manifest": _sha256(manifest_out_path),
    }
    _write_json(sha_path, sha_payload)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": built.get("status"),
        "total_tasks": len(tasks),
        "library_count": built.get("library_count"),
        "model_count": built.get("model_count"),
        "counts_by_library": built.get("counts_by_library"),
        "counts_by_failure_type": built.get("counts_by_failure_type"),
        "counts_by_category": built.get("counts_by_category"),
        "counts_by_scale": built.get("counts_by_scale"),
        "split_counts": built.get("split_counts"),
        "provenance_completeness_pct": built.get("provenance_completeness_pct"),
        "library_hints_nonempty_pct": built.get("library_hints_nonempty_pct"),
        "taskset_unfrozen_path": str(taskset_unfrozen_path),
        "taskset_frozen_path": str(taskset_frozen_path),
        "manifest_path": str(manifest_out_path),
        "exclude_models_path": built.get("exclude_models_path"),
        "excluded_model_count": built.get("excluded_model_count"),
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
