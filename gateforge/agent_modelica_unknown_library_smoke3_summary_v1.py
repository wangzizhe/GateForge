from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_unknown_library_smoke3_summary_v1"
REQUIRED_RECORD_FIELDS = ("task_id", "passed", "error_message", "stderr_snippet", "attempts")


def _load_json(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _task_library_id(task: dict) -> str:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    return _norm(source_meta.get("library_id") or task.get("source_library") or "unknown").lower()


def build_smoke_summary(
    *,
    taskset_payload: dict,
    results_payload: dict,
    records_payload: list[dict],
    per_task_time_budget_sec: float,
    min_tasks_within_budget: int,
) -> dict:
    tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
    results_rows = results_payload.get("records") if isinstance(results_payload.get("records"), list) else []
    records = records_payload or [row for row in results_rows if isinstance(row, dict)]
    total_tasks = len(tasks)

    counts_by_library: dict[str, int] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        library_id = _task_library_id(task)
        counts_by_library[library_id] = int(counts_by_library.get(library_id) or 0) + 1

    missing_fields: dict[str, list[str]] = {}
    failed_without_signal: list[str] = []
    within_budget_count = 0
    success_count = 0
    for row in records:
        if not isinstance(row, dict):
            continue
        task_id = _norm(row.get("task_id"))
        missing = [field for field in REQUIRED_RECORD_FIELDS if field not in row]
        if missing:
            missing_fields[task_id or "unknown"] = missing
        elapsed_sec = row.get("elapsed_sec")
        if isinstance(elapsed_sec, (int, float)) and float(elapsed_sec) <= float(per_task_time_budget_sec):
            within_budget_count += 1
        if bool(row.get("passed")):
            success_count += 1
        if not bool(row.get("passed")):
            has_signal = bool(_norm(row.get("error_message")) or _norm(row.get("stderr_snippet")) or row.get("attempts"))
            if not has_signal:
                failed_without_signal.append(task_id)

    reasons: list[str] = []
    if total_tasks <= 0:
        reasons.append("smoke_taskset_empty")
    if len(records) != total_tasks:
        reasons.append(f"incomplete_records:{len(records)}/{total_tasks}")
    if missing_fields:
        reasons.append("records_missing_required_fields")
    if within_budget_count < max(0, int(min_tasks_within_budget)):
        reasons.append(
            f"tasks_within_time_budget_below_threshold:{within_budget_count}/{int(min_tasks_within_budget)}"
        )
    if failed_without_signal:
        reasons.append("failed_tasks_without_diagnostic_signal")

    status = "PASS"
    if reasons:
        status = "NEEDS_REVIEW" if total_tasks > 0 and len(records) == total_tasks else "FAIL"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": total_tasks,
        "completed_records": len(records),
        "success_count": success_count,
        "success_at_k_pct": round((100.0 * success_count / total_tasks), 2) if total_tasks else 0.0,
        "records_have_required_fields": not bool(missing_fields),
        "missing_required_fields": missing_fields,
        "tasks_within_time_budget_count": within_budget_count,
        "per_task_time_budget_sec": float(per_task_time_budget_sec),
        "min_tasks_within_budget": int(min_tasks_within_budget),
        "tasks_within_time_budget_ok": within_budget_count >= max(0, int(min_tasks_within_budget)),
        "failed_tasks_with_explicit_signal_ok": not bool(failed_without_signal),
        "failed_tasks_without_signal": failed_without_signal,
        "counts_by_library": counts_by_library,
        "records_jsonl_count": len(records_payload),
        "results_record_count": len(results_rows),
        "reasons": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess a 3-task unknown-library live smoke run")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--records-jsonl", required=True)
    parser.add_argument("--per-task-time-budget-sec", type=float, default=300.0)
    parser.add_argument("--min-tasks-within-budget", type=int, default=2)
    parser.add_argument("--out", default="artifacts/agent_modelica_unknown_library_smoke3_summary_v1/summary.json")
    args = parser.parse_args()

    summary = build_smoke_summary(
        taskset_payload=_load_json(args.taskset),
        results_payload=_load_json(args.results),
        records_payload=_load_jsonl(args.records_jsonl),
        per_task_time_budget_sec=float(args.per_task_time_budget_sec),
        min_tasks_within_budget=int(args.min_tasks_within_budget),
    )
    _write_json(Path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "success_count": summary.get("success_count"), "total_tasks": summary.get("total_tasks")}))


if __name__ == "__main__":
    main()
