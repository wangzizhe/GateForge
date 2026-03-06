from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

TARGET_FAILURE_TYPE = "script_parse_error"
INJECTED_STATE_TOKEN = "__gf_state_"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Script Parse Focus Taskset v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- selected_count: `{payload.get('selected_count')}`",
        f"- target_failure_type: `{payload.get('target_failure_type')}`",
        "",
        "## Selection Reasons",
        "",
    ]
    reasons = payload.get("selection_reason_counts") if isinstance(payload.get("selection_reason_counts"), dict) else {}
    if reasons:
        for key in sorted(reasons.keys()):
            lines.append(f"- {key}: `{reasons[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _task_id_set_from_first_attr(payload: dict, target_failure_type: str) -> set[str]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        observed = str(row.get("first_observed_failure_type") or "").strip().lower()
        if observed == target_failure_type:
            task_id = str(row.get("task_id") or "").strip()
            if task_id:
                out.add(task_id)
    return out


def _task_id_set_from_run_results(payload: dict, target_failure_type: str) -> set[str]:
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    out: set[str] = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        task_id = str(rec.get("task_id") or "").strip()
        if not task_id:
            continue
        attempts = rec.get("attempts") if isinstance(rec.get("attempts"), list) else []
        first = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
        observed = str(first.get("observed_failure_type") or "").strip().lower()
        if observed == target_failure_type:
            out.add(task_id)
    return out


def _contains_injected_state_token(task: dict) -> bool:
    raw_path = str(task.get("mutated_model_path") or "").strip()
    if not raw_path:
        return False
    model_path = Path(raw_path)
    if not model_path.exists() or not model_path.is_file():
        return False
    try:
        text = model_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = model_path.read_text(encoding="latin-1")
    return INJECTED_STATE_TOKEN in text


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a focused taskset for script_parse_error from recent run signals")
    parser.add_argument("--taskset-in", required=True)
    parser.add_argument("--run-results", default="")
    parser.add_argument("--first-failure-attribution", default="")
    parser.add_argument("--target-failure-type", default=TARGET_FAILURE_TYPE)
    parser.add_argument("--min-tasks", type=int, default=3)
    parser.add_argument("--max-tasks", type=int, default=6)
    parser.add_argument("--out-taskset", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_script_parse_focus_taskset_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    target_failure_type = str(args.target_failure_type or TARGET_FAILURE_TYPE).strip().lower()
    taskset = _load_json(args.taskset_in)
    tasks = taskset.get("tasks") if isinstance(taskset.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]

    from_first = _task_id_set_from_first_attr(_load_json(args.first_failure_attribution), target_failure_type) if str(args.first_failure_attribution).strip() else set()
    from_run = _task_id_set_from_run_results(_load_json(args.run_results), target_failure_type) if str(args.run_results).strip() else set()
    selected: list[dict] = []
    selected_ids: set[str] = set()
    reason_counts: dict[str, int] = {}

    def add_task(task: dict, reason: str) -> None:
        task_id = str(task.get("task_id") or "").strip()
        if not task_id or task_id in selected_ids:
            return
        selected_ids.add(task_id)
        item = dict(task)
        item["_focus_reason"] = reason
        selected.append(item)
        reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1

    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        if task_id and task_id in from_first:
            add_task(task, "first_observed_script_parse_error")
    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        if task_id and task_id in from_run:
            add_task(task, "run_results_first_attempt_script_parse_error")

    min_tasks = max(0, int(args.min_tasks))
    max_tasks = max(1, int(args.max_tasks))
    if len(selected) < min_tasks:
        for task in tasks:
            if len(selected) >= min_tasks:
                break
            if _contains_injected_state_token(task):
                add_task(task, "contains_injected_state_token")

    selected = selected[:max_tasks]

    out_taskset = {
        "schema_version": "agent_modelica_script_parse_focus_taskset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_failure_type": target_failure_type,
        "tasks": selected,
        "sources": {
            "taskset_in": args.taskset_in,
            "run_results": args.run_results if str(args.run_results).strip() else None,
            "first_failure_attribution": args.first_failure_attribution if str(args.first_failure_attribution).strip() else None,
        },
    }
    _write_json(args.out_taskset, out_taskset)

    summary = {
        "schema_version": "agent_modelica_script_parse_focus_taskset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if selected else "NEEDS_REVIEW",
        "target_failure_type": target_failure_type,
        "selected_count": len(selected),
        "min_tasks": min_tasks,
        "max_tasks": max_tasks,
        "selection_reason_counts": reason_counts,
        "out_taskset": args.out_taskset,
        "sources": out_taskset["sources"],
        "reasons": [] if selected else ["no_script_parse_focus_tasks_found"],
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "selected_count": summary.get("selected_count")}))


if __name__ == "__main__":
    main()
