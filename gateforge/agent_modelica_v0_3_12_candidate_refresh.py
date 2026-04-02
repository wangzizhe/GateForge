from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_12_candidate_refresh"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_candidate_refresh"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _result_rows(payload: dict) -> list[dict]:
    rows = payload.get("results")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("item_id") or row.get("mutation_id"))


def _attempt_rows(detail: dict) -> list[dict]:
    rows = detail.get("attempts")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _executor_runtime_hygiene(detail: dict) -> dict:
    payload = detail.get("executor_runtime_hygiene")
    return dict(payload) if isinstance(payload, dict) else {}


def _candidate_parameters(attempt: dict) -> list[str]:
    for field in ("replan_candidate_parameters", "llm_plan_candidate_parameters"):
        rows = attempt.get(field)
        if isinstance(rows, list):
            out = [_norm(item) for item in rows if _norm(item)]
            if out:
                return out
    return []


def _candidate_branch_rows(task: dict, result: dict) -> list[dict]:
    for field in ("candidate_next_branches", "candidate_branches"):
        rows = result.get(field)
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict)]
        rows = task.get(field)
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict)]
    return []


def _branch_support_map(branch_rows: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in branch_rows:
        branch_id = _norm(row.get("branch_id"))
        params = {
            _norm(item)
            for item in (row.get("supporting_parameters") or [])
            if _norm(item)
        }
        if branch_id:
            out[branch_id] = params
    return out


def _detect_branch_for_attempt(branch_support: dict[str, set[str]], attempt: dict) -> str:
    params = _candidate_parameters(attempt)
    if not params:
        return ""
    first = params[0]
    for branch_id, supported in branch_support.items():
        if first in supported:
            return branch_id
    matching = [branch_id for branch_id, supported in branch_support.items() if any(param in supported for param in params)]
    if len(matching) == 1:
        return matching[0]
    return ""


def _derive_branch_sequence(*, task: dict, detail: dict) -> list[str]:
    branch_rows = _candidate_branch_rows(task, {})
    branch_support = _branch_support_map(branch_rows)
    sequence: list[str] = []
    for attempt in _attempt_rows(detail):
        branch_id = _detect_branch_for_attempt(branch_support, attempt)
        if branch_id and (not sequence or sequence[-1] != branch_id):
            sequence.append(branch_id)
    return sequence


def refresh_v0_3_12_candidates(
    *,
    candidate_taskset_path: str,
    results_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    taskset = _load_json(candidate_taskset_path)
    results_payload = _load_json(results_path)
    tasks = _task_rows(taskset)
    results_index = {_item_id(row): row for row in _result_rows(results_payload) if _item_id(row)}

    refreshed_rows = []
    matched_result_count = 0
    successful_case_count = 0
    planner_event_case_count = 0
    repair_safety_blocked_case_count = 0
    rollback_applied_case_count = 0
    planner_experience_context_truncated_case_count = 0
    replan_context_truncated_case_count = 0

    for task in tasks:
        item_id = _item_id(task)
        result = dict(results_index.get(item_id, {}) or {})
        detail = _load_json(result.get("result_json_path") or "")
        if result:
            matched_result_count += 1
        runtime_hygiene = _executor_runtime_hygiene(detail)
        if int(runtime_hygiene.get("planner_event_count") or 0) > 0:
            planner_event_case_count += 1
        if int(runtime_hygiene.get("repair_safety_blocked_count") or 0) > 0:
            repair_safety_blocked_case_count += 1
        if int(runtime_hygiene.get("rollback_applied_count") or 0) > 0:
            rollback_applied_case_count += 1
        if int(runtime_hygiene.get("planner_experience_context_truncated_count") or 0) > 0:
            planner_experience_context_truncated_case_count += 1
        if int(runtime_hygiene.get("replan_context_truncated_count") or 0) > 0:
            replan_context_truncated_case_count += 1

        verdict = _norm(result.get("verdict") or detail.get("executor_status"))
        success = verdict.upper() == "PASS"
        if success:
            successful_case_count += 1
        detected_branch_sequence = _derive_branch_sequence(task=task, detail=detail)
        merged = {
            **task,
            **result,
            "item_id": item_id,
            "result_json_path": _norm(result.get("result_json_path")),
            "verdict": _norm(result.get("verdict") or detail.get("executor_status")),
            "executor_status": _norm(detail.get("executor_status") or result.get("executor_status")),
            "detected_branch_sequence": detected_branch_sequence,
            "executor_runtime_hygiene": runtime_hygiene,
            "attempt_count": len(_attempt_rows(detail)),
        }
        refreshed_rows.append(merged)

    metrics = {
        "total_rows": len(refreshed_rows),
        "matched_result_count": matched_result_count,
        "successful_case_count": successful_case_count,
        "planner_event_case_count": planner_event_case_count,
        "repair_safety_blocked_case_count": repair_safety_blocked_case_count,
        "rollback_applied_case_count": rollback_applied_case_count,
        "planner_experience_context_truncated_case_count": planner_experience_context_truncated_case_count,
        "replan_context_truncated_case_count": replan_context_truncated_case_count,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if refreshed_rows else "EMPTY",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "results_path": str(Path(results_path).resolve()) if Path(results_path).exists() else str(results_path),
        "metrics": metrics,
        "tasks": refreshed_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "taskset_candidates_refreshed.json", {"tasks": refreshed_rows})
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.12 Candidate Refresh",
                "",
                f"- status: `{payload.get('status')}`",
                f"- total_rows: `{metrics.get('total_rows')}`",
                f"- successful_case_count: `{metrics.get('successful_case_count')}`",
                f"- planner_event_case_count: `{metrics.get('planner_event_case_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the v0.3.12 candidate lane with live results.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = refresh_v0_3_12_candidates(
        candidate_taskset_path=str(args.candidate_taskset),
        results_path=str(args.results),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
