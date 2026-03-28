from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_layer4_holdout_pack_v0_3_1"
DEFAULT_TASKSET_PATH = "artifacts/agent_modelica_layer4_holdout_v0_3_1/taskset_frozen.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_layer4_holdout_pack_v0_3_1"


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _package_name(task: dict) -> str:
    meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    package_name = _norm(meta.get("package_name"))
    if package_name:
        return package_name
    qualified = _norm(meta.get("qualified_model_name"))
    if "." in qualified:
        return qualified.split(".", 1)[0].strip()
    return ""


def _extra_model_loads(tasks: list[dict]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        name = _package_name(task)
        if name and name not in {"Modelica"} and name not in seen:
            seen.add(name)
            items.append(name)
    return items


def _case_row(task: dict) -> dict:
    meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    return {
        "mutation_id": _norm(task.get("task_id")),
        "target_scale": _norm(task.get("scale")),
        "expected_failure_type": _norm(task.get("failure_type")),
        "expected_stage": _norm(task.get("expected_stage")),
        "mutated_model_path": _norm(task.get("mutated_model_path")),
        "source_model_path": _norm(task.get("source_model_path")),
        "source_library_path": _norm(meta.get("accepted_source_path") or meta.get("local_path")),
        "source_package_name": _package_name(task),
        "source_library_model_path": _norm(meta.get("model_path")),
        "source_qualified_model_name": _norm(meta.get("qualified_model_name")),
        "source_library": _norm(task.get("source_library")),
        "domain": _norm(task.get("domain")),
        "difficulty_layer": _norm(task.get("expected_layer_hint") or "layer_4"),
        "family_id": _norm(task.get("v0_3_family_id")),
        "split": _norm(task.get("split")),
    }


def build_layer4_holdout_pack_v0_3_1(
    *,
    taskset_path: str = DEFAULT_TASKSET_PATH,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    taskset = _load_json(taskset_path)
    tasks = [dict(row) for row in (taskset.get("tasks") or []) if isinstance(row, dict) and _norm(row.get("task_id"))]
    cases = [_case_row(task) for task in tasks]
    extra_model_loads = _extra_model_loads(tasks)

    out_root = Path(out_dir)
    hardpack_path = out_root / "hardpack_frozen.json"
    hardpack = {
        "schema_version": "agent_modelica_hardpack_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hardpack_version": "agent_modelica_layer4_holdout_pack_v0_3_1",
        "fixture_mode": "holdout",
        "source_taskset": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "library_load_models": extra_model_loads,
        "case_count": len(cases),
        "cases": cases,
    }
    _write_json(hardpack_path, hardpack)

    family_counts: dict[str, int] = {}
    for case in cases:
        family_id = _norm(case.get("family_id") or "unknown_family")
        family_counts[family_id] = int(family_counts.get(family_id) or 0) + 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if cases else "FAIL",
        "task_count": len(tasks),
        "case_count": len(cases),
        "hardpack_path": str(hardpack_path.resolve()),
        "source_taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "library_load_models": extra_model_loads,
        "family_counts": dict(sorted(family_counts.items())),
    }
    _write_json(out_root / "summary.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert the v0.3.1 Layer 4 holdout taskset into a GF hardpack.")
    parser.add_argument("--taskset", default=DEFAULT_TASKSET_PATH)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_layer4_holdout_pack_v0_3_1(taskset_path=str(args.taskset), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "case_count": int(payload.get("case_count") or 0)}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
