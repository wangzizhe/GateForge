from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_difficulty_layer_sidecar_builder_v1 import build_sidecar


SCHEMA_VERSION = "agent_modelica_planner_sensitive_taskset_builder_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    payload = json.loads(p.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _score_record(record: dict) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    llm_request_count_delta = int(record.get("llm_request_count_delta") or 0)
    llm_plan_used = bool(record.get("llm_plan_used"))
    llm_plan_generated = bool(record.get("llm_plan_generated"))
    passed = bool(record.get("passed"))
    failure_type = str(record.get("failure_type") or "").strip().lower()
    stage = str(record.get("current_stage") or record.get("multi_step_stage") or "").strip().lower()
    rounds_used = int(record.get("rounds_used") or 0)

    if not (llm_request_count_delta > 0 or llm_plan_used or llm_plan_generated):
        return 0, []

    if llm_request_count_delta > 0:
        reasons.append("llm_request_count_positive")
        score += 3
    if llm_plan_used:
        reasons.append("llm_plan_used")
        score += 3
    if llm_plan_generated:
        reasons.append("llm_plan_generated")
        score += 2
    if passed:
        reasons.append("passed")
        score += 1
    if rounds_used > 1:
        reasons.append("multi_round")
        score += 1
    if failure_type in {"stability_then_behavior", "behavior_then_robustness"}:
        reasons.append("planner_sensitive_family")
        score += 2
    if stage in {"stage_2", "stage_2_resolution"}:
        reasons.append("stage_2_context")
        score += 1

    return score, reasons


def build_planner_sensitive_taskset(
    *,
    results_paths: list[str],
    taskset_paths: list[str],
    out_taskset_path: str,
    max_tasks: int = 24,
    planner_invoked_target_pct: float = 50.0,
    out_layer_sidecar_path: str = "",
) -> dict:
    task_by_id: dict[str, dict] = {}
    task_sources: dict[str, str] = {}
    missing_tasksets: list[str] = []
    for path in taskset_paths:
        payload = _load_json(path)
        if not payload:
            missing_tasksets.append(str(path))
            continue
        for task in payload.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id") or "").strip()
            if not task_id or task_id in task_by_id:
                continue
            task_by_id[task_id] = task
            task_sources[task_id] = str(path)

    selected_rows: list[dict] = []
    seen: set[str] = set()
    missing_results: list[str] = []
    for path in results_paths:
        payload = _load_json(path)
        if not payload:
            missing_results.append(str(path))
            continue
        for record in payload.get("records") or []:
            if not isinstance(record, dict):
                continue
            task_id = str(record.get("task_id") or "").strip()
            if not task_id or task_id in seen or task_id not in task_by_id:
                continue
            score, reasons = _score_record(record)
            if score <= 0:
                continue
            seen.add(task_id)
            selected_rows.append(
                {
                    "task_id": task_id,
                    "failure_type": str(record.get("failure_type") or ""),
                    "rounds_used": int(record.get("rounds_used") or 0),
                    "llm_request_count_delta": int(record.get("llm_request_count_delta") or 0),
                    "llm_plan_used": bool(record.get("llm_plan_used")),
                    "llm_plan_generated": bool(record.get("llm_plan_generated")),
                    "passed": bool(record.get("passed")),
                    "selection_score": score,
                    "selection_reasons": reasons,
                    "source_results_path": str(path),
                    "source_taskset_path": task_sources.get(task_id, ""),
                }
            )

    selected_rows.sort(
        key=lambda row: (
            -int(row.get("llm_request_count_delta") or 0),
            -int(row.get("selection_score") or 0),
            -int(row.get("rounds_used") or 0),
            str(row.get("task_id") or ""),
        )
    )
    if int(max_tasks or 0) > 0:
        selected_rows = selected_rows[: int(max_tasks)]

    selected_tasks = [task_by_id[str(row.get("task_id") or "")] for row in selected_rows if str(row.get("task_id") or "") in task_by_id]
    planner_invoked_count = len([row for row in selected_rows if bool(row.get("llm_request_count_delta") or row.get("llm_plan_used"))])
    planner_invoked_rate_pct = round((planner_invoked_count / len(selected_rows)) * 100.0, 2) if selected_rows else 0.0

    if not selected_rows:
        status = "FAIL"
        validation_reason = "no_planner_sensitive_tasks"
    elif planner_invoked_rate_pct < float(planner_invoked_target_pct):
        status = "NEEDS_REVIEW"
        validation_reason = "planner_invoked_rate_below_target"
    else:
        status = "PASS"
        validation_reason = "planner_invoked_rate_met"

    layer_sidecar_path = str(out_layer_sidecar_path or Path(out_taskset_path).with_name("layer_metadata.json"))
    taskset_payload = {
        "schema_version": "agent_modelica_taskset_frozen_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "planner_sensitive_metadata": {
            "schema_version": SCHEMA_VERSION,
            "results_paths": [str(path) for path in results_paths],
            "taskset_paths": [str(path) for path in taskset_paths],
            "planner_invoked_target_pct": float(planner_invoked_target_pct),
            "planner_invoked_rate_pct": planner_invoked_rate_pct,
            "selection_count": len(selected_rows),
            "validation_status": status,
            "validation_reason": validation_reason,
            "layer_sidecar_path": layer_sidecar_path,
        },
        "task_count": len(selected_tasks),
        "tasks": selected_tasks,
    }
    _write_json(out_taskset_path, taskset_payload)
    layer_sidecar_summary = build_sidecar(
        substrate_path=str(out_taskset_path),
        results_paths=[str(path) for path in results_paths],
        out_sidecar=layer_sidecar_path,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "validation_reason": validation_reason,
        "results_paths": [str(path) for path in results_paths],
        "taskset_paths": [str(path) for path in taskset_paths],
        "out_taskset_path": str(out_taskset_path),
        "planner_invoked_target_pct": float(planner_invoked_target_pct),
        "planner_invoked_rate_pct": planner_invoked_rate_pct,
        "layer_sidecar_path": layer_sidecar_path,
        "layer_sidecar_summary": layer_sidecar_summary,
        "selected_task_count": len(selected_rows),
        "selected_rows": selected_rows,
        "missing_results": missing_results,
        "missing_tasksets": missing_tasksets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a planner-sensitive taskset from historical run-contract results")
    parser.add_argument("--results", action="append", default=[])
    parser.add_argument("--taskset", action="append", default=[])
    parser.add_argument("--out-taskset", required=True)
    parser.add_argument("--out-summary", default="")
    parser.add_argument("--max-tasks", type=int, default=24)
    parser.add_argument("--planner-invoked-target-pct", type=float, default=50.0)
    parser.add_argument("--out-layer-sidecar", default="")
    args = parser.parse_args()

    out_summary = str(args.out_summary or "")
    if not out_summary:
        out_summary = str(Path(args.out_taskset).with_name("planner_sensitive_taskset_summary.json"))
    summary = build_planner_sensitive_taskset(
        results_paths=[str(path) for path in (args.results or []) if str(path).strip()],
        taskset_paths=[str(path) for path in (args.taskset or []) if str(path).strip()],
        out_taskset_path=str(args.out_taskset),
        max_tasks=int(args.max_tasks or 0),
        planner_invoked_target_pct=float(args.planner_invoked_target_pct or 0.0),
        out_layer_sidecar_path=str(args.out_layer_sidecar or ""),
    )
    _write_json(out_summary, summary)
    print(json.dumps({"status": summary.get("status"), "selected_task_count": summary.get("selected_task_count")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
