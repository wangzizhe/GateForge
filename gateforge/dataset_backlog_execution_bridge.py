from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _task_template(task: dict) -> dict:
    task_id = str(task.get("task_id") or "")
    reason = str(task.get("reason") or "")
    priority = str(task.get("priority") or "P3")
    title = str(task.get("title") or task_id)

    if "failure_type" in task_id or reason == "taxonomy_missing_failure_type":
        workstream = "dataset_expansion"
        acceptance = [
            "Add >=1 reproducible case for target failure type",
            "Update taxonomy coverage summary and verify missing type removed",
            "Attach minimal replay evidence",
        ]
    elif "model_scale" in task_id:
        workstream = "scale_coverage"
        acceptance = [
            "Add representative model case for target scale",
            "Update model scale counts in taxonomy/registry",
            "Run fast governance snapshot demo and verify signal update",
        ]
    elif reason in {"distribution_drift_exceeds_threshold", "false_positive_rate_high", "regression_rate_high"}:
        workstream = "benchmark_tuning"
        acceptance = [
            "Run before/after benchmark and capture metric deltas",
            "Reduce target risk metric below threshold",
            "Publish replay evaluator summary",
        ]
    else:
        workstream = "governance_hardening"
        acceptance = [
            "Implement targeted fix with reproducible artifact",
            "Validate contract/demo remains PASS",
            "Document outcome in evidence pack",
        ]

    owner = "policy_ops" if priority in {"P0", "P1"} else "dataset_ops"
    eta_days = 2 if priority == "P0" else (4 if priority == "P1" else (7 if priority == "P2" else 10))

    return {
        "execution_id": f"exec.{task_id}",
        "source_task_id": task_id,
        "title": title,
        "priority": priority,
        "workstream": workstream,
        "owner": owner,
        "eta_days": eta_days,
        "acceptance_criteria": acceptance,
        "status": "READY",
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Backlog Execution Bridge",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_execution_tasks: `{payload.get('total_execution_tasks')}`",
        f"- ready_count: `{payload.get('ready_count')}`",
        f"- blocked_count: `{payload.get('blocked_count')}`",
        "",
        "## Top Execution Tasks",
        "",
    ]
    tasks = payload.get("execution_tasks") if isinstance(payload.get("execution_tasks"), list) else []
    if tasks:
        for row in tasks[:12]:
            lines.append(
                f"- `{row.get('priority')}` `{row.get('execution_id')}` owner=`{row.get('owner')}` eta_days=`{row.get('eta_days')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert blind-spot backlog into executable task plan")
    parser.add_argument("--backlog-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_backlog_execution_bridge/summary.json")
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--max-tasks", type=int, default=20)
    args = parser.parse_args()

    backlog = _load_json(args.backlog_summary)
    tasks_value = backlog.get("tasks")
    tasks_valid = isinstance(tasks_value, list)
    tasks = tasks_value if tasks_valid else []
    execution_tasks = [_task_template(t) for t in tasks[: max(0, int(args.max_tasks))] if isinstance(t, dict)]

    ready_count = len([x for x in execution_tasks if x.get("status") == "READY"])
    blocked_count = len([x for x in execution_tasks if x.get("status") == "BLOCKED"])

    status = "PASS" if not execution_tasks else "NEEDS_REVIEW"
    if not tasks_valid:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_execution_tasks": len(execution_tasks),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "source_backlog_task_count": _to_int(backlog.get("total_open_tasks", len(tasks))),
        "execution_tasks": execution_tasks,
        "sources": {"backlog_summary": args.backlog_summary},
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "total_execution_tasks": payload.get("total_execution_tasks")}))
    if payload.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
