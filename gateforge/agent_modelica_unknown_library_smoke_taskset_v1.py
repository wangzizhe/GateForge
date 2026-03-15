from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_unknown_library_smoke_taskset_v1"


def _load_json(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _task_library_id(task: dict) -> str:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    return _norm(source_meta.get("library_id") or task.get("source_library") or "unknown").lower()


def build_smoke_taskset(*, payload: dict, requested_task_ids: list[str]) -> tuple[dict, dict]:
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    ordered_ids = []
    seen: set[str] = set()
    for value in requested_task_ids:
        task_id = _norm(value)
        if task_id and task_id not in seen:
            ordered_ids.append(task_id)
            seen.add(task_id)

    task_by_id = {str(row.get("task_id") or "").strip(): row for row in tasks if isinstance(row, dict)}
    selected = [task_by_id[task_id] for task_id in ordered_ids if task_id in task_by_id]
    missing = [task_id for task_id in ordered_ids if task_id not in task_by_id]

    counts_by_library: dict[str, int] = {}
    for task in selected:
        library_id = _task_library_id(task)
        counts_by_library[library_id] = int(counts_by_library.get(library_id) or 0) + 1

    reasons: list[str] = []
    if missing:
        reasons.extend([f"missing_task_id:{task_id}" for task_id in missing])
    if not selected:
        reasons.append("selected_taskset_empty")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if selected and not missing else "FAIL",
        "requested_task_ids": ordered_ids,
        "selected_task_ids": [str(task.get("task_id") or "") for task in selected],
        "missing_task_ids": missing,
        "total_tasks": len(selected),
        "library_count": len(counts_by_library),
        "counts_by_library": counts_by_library,
        "reasons": reasons,
    }

    out_taskset = dict(payload)
    out_taskset["tasks"] = selected
    out_taskset["summary"] = {
        "schema_version": SCHEMA_VERSION,
        "total_selected_tasks": len(selected),
        "requested_task_ids": ordered_ids,
    }
    return out_taskset, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a 3-task unknown-library smoke taskset from a frozen taskset")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--task-ids-csv", required=True)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_unknown_library_smoke_taskset_v1")
    args = parser.parse_args()

    payload = _load_json(args.taskset)
    requested_task_ids = [item.strip() for item in str(args.task_ids_csv or "").split(",") if item.strip()]
    taskset, summary = build_smoke_taskset(payload=payload, requested_task_ids=requested_task_ids)

    out_dir = Path(args.out_dir)
    taskset_path = out_dir / "taskset_frozen.json"
    summary_path = out_dir / "summary.json"
    _write_json(taskset_path, taskset)
    _write_json(summary_path, summary)

    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "total_tasks": summary.get("total_tasks"),
                "taskset_frozen_path": str(taskset_path),
                "summary_path": str(summary_path),
            }
        )
    )


if __name__ == "__main__":
    main()
