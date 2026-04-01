from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_branch_switch_candidate_refresh_v0_3_8"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_candidate_refresh_v0_3_8"


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
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _bool_or_unset(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = _norm(value).lower()
    if text in {"", "unset", "unknown", "none"}:
        return None
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return None


def _candidate_branch_rows(task: dict, result: dict) -> list[dict]:
    rows = result.get("candidate_branches")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    rows = task.get("candidate_branches")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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


def _attempt_rows(detail: dict) -> list[dict]:
    rows = detail.get("attempts")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _candidate_parameters(attempt: dict) -> list[str]:
    for field in ("replan_candidate_parameters", "llm_plan_candidate_parameters"):
        rows = attempt.get(field)
        if isinstance(rows, list):
            out = [_norm(item) for item in rows if _norm(item)]
            if out:
                return out
    return []


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
    branch_rows = _candidate_branch_rows(task, detail)
    branch_support = _branch_support_map(branch_rows)
    sequence: list[str] = []
    for attempt in _attempt_rows(detail):
        branch_id = _detect_branch_for_attempt(branch_support, attempt)
        if branch_id:
            if not sequence or sequence[-1] != branch_id:
                sequence.append(branch_id)
    return sequence


def _derive_branch_evidence(*, task: dict, result: dict, detail: dict) -> dict:
    sequence = _derive_branch_sequence(task=task, detail=detail)
    success = _norm(result.get("verdict")).upper() == "PASS" or _norm(result.get("executor_status")).upper() == "PASS"
    current_branch = _norm(result.get("current_branch") or task.get("current_branch"))
    preferred_branch = _norm(result.get("preferred_branch") or task.get("preferred_branch"))
    branch_rows = _candidate_branch_rows(task, result)
    selected_branch = ""
    abandoned_branch = ""
    if len(sequence) >= 2:
        abandoned_branch = sequence[-2]
        selected_branch = sequence[-1]
    elif len(sequence) == 1:
        selected_branch = sequence[0]
    branch_switch_event = len(sequence) >= 2 and selected_branch != abandoned_branch and bool(selected_branch)
    stall_event = bool(result.get("planner_invoked")) and int(result.get("rounds_used") or 0) >= 3 and len(sequence) >= 2
    wrong_branch_event = bool(branch_switch_event and abandoned_branch == current_branch)
    correct_branch_selected = None
    if branch_switch_event and success:
        correct_branch_selected = bool(selected_branch == preferred_branch)
    elif branch_switch_event and not success:
        correct_branch_selected = False
    branch_switch_contributed = None
    if success and branch_switch_event:
        branch_switch_contributed = bool(selected_branch == preferred_branch and stall_event)
    elif success and not branch_switch_event:
        branch_switch_contributed = False
    return {
        "candidate_next_branches": branch_rows,
        "detected_branch_sequence": sequence,
        "stall_event_observed": True if stall_event else False if bool(result) else None,
        "wrong_branch_event_observed": True if wrong_branch_event else False if branch_switch_event or success else None,
        "branch_switch_event_observed": True if branch_switch_event else False if bool(sequence) or success else None,
        "selected_branch": selected_branch or "",
        "abandoned_branch": abandoned_branch or "",
        "wrong_branch_entered": True if wrong_branch_event else False if branch_switch_event or success else None,
        "correct_branch_selected": correct_branch_selected,
        "branch_switch_contributed_to_success": branch_switch_contributed,
        "success_after_branch_switch": bool(success and branch_switch_contributed is True),
        "success_without_branch_switch_evidence": bool(success and branch_switch_contributed is not True),
    }


def refresh_branch_switch_candidates(
    *,
    candidate_taskset_path: str,
    results_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    taskset = _load_json(candidate_taskset_path)
    results_payload = _load_json(results_path)
    tasks = _task_rows(taskset)
    results_index = {_item_id(row): row for row in _result_rows(results_payload) if _item_id(row)}
    top_protocol = (
        results_payload.get("baseline_measurement_protocol")
        if isinstance(results_payload.get("baseline_measurement_protocol"), dict)
        else {}
    )

    refreshed_rows = []
    matched_result_count = 0
    planner_invoked_count = 0
    deterministic_only_count = 0
    success_after_switch_count = 0
    success_without_evidence_count = 0
    stalled_count = 0
    wrong_branch_count = 0
    successful_case_count = 0

    frozen_mainline_task_ids = [_item_id(row) for row in tasks if _item_id(row)]

    for task in tasks:
        item_id = _item_id(task)
        result = dict(results_index.get(item_id, {}) or {})
        detail = _load_json(result.get("result_json_path") or "")
        if result:
            matched_result_count += 1
        protocol = (
            result.get("baseline_measurement_protocol")
            if isinstance(result.get("baseline_measurement_protocol"), dict)
            else task.get("baseline_measurement_protocol")
        ) or top_protocol
        evidence = _derive_branch_evidence(task=task, result=result, detail=detail)
        merged = {
            **task,
            "verdict": _norm(result.get("verdict") or task.get("verdict")),
            "executor_status": _norm(result.get("executor_status") or task.get("executor_status")),
            "resolution_path": _norm(result.get("resolution_path") or task.get("resolution_path")),
            "planner_invoked": result.get("planner_invoked") if "planner_invoked" in result else task.get("planner_invoked"),
            "rounds_used": int(result.get("rounds_used") or task.get("rounds_used") or 0),
            "llm_request_count": int(result.get("llm_request_count") or task.get("llm_request_count") or 0),
            "check_model_pass": result.get("check_model_pass") if "check_model_pass" in result else task.get("check_model_pass"),
            "simulate_pass": result.get("simulate_pass") if "simulate_pass" in result else task.get("simulate_pass"),
            "error_message": _norm(result.get("error_message") or task.get("error_message")),
            "result_json_path": _norm(result.get("result_json_path")),
            "baseline_measurement_protocol": protocol,
            **evidence,
        }
        if merged.get("planner_invoked") is True:
            planner_invoked_count += 1
        if _norm(merged.get("resolution_path")) == "deterministic_rule_only":
            deterministic_only_count += 1
        if _norm(merged.get("verdict")).upper() == "PASS" or _norm(merged.get("executor_status")).upper() == "PASS":
            successful_case_count += 1
        if merged.get("stall_event_observed") is True:
            stalled_count += 1
        if merged.get("wrong_branch_entered") is True:
            wrong_branch_count += 1
        if merged.get("success_after_branch_switch") is True:
            success_after_switch_count += 1
        if bool(merged.get("success_without_branch_switch_evidence")):
            success_without_evidence_count += 1
        refreshed_rows.append(merged)

    total = len(refreshed_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "results_path": str(Path(results_path).resolve()) if Path(results_path).exists() else str(results_path),
        "frozen_mainline_task_ids": frozen_mainline_task_ids,
        "metrics": {
            "total_rows": total,
            "matched_result_count": matched_result_count,
            "planner_invoked_count": planner_invoked_count,
            "planner_invoked_pct": round(100.0 * planner_invoked_count / total, 1) if total else 0.0,
            "deterministic_only_count": deterministic_only_count,
            "deterministic_only_pct": round(100.0 * deterministic_only_count / total, 1) if total else 0.0,
            "successful_case_count": successful_case_count,
            "stall_event_observed_count": stalled_count,
            "wrong_branch_after_restore_count": wrong_branch_count,
            "success_after_branch_switch_count": success_after_switch_count,
            "success_without_branch_switch_evidence_count": success_without_evidence_count,
            "success_without_branch_switch_evidence_pct": round(100.0 * success_without_evidence_count / total, 1) if total else 0.0,
            "branch_switch_evidenced_success_pct": round(100.0 * success_after_switch_count / successful_case_count, 1) if successful_case_count else 0.0,
        },
        "tasks": refreshed_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "taskset_candidates_refreshed.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    return "\n".join(
        [
            "# v0.3.8 Branch-Switch Candidate Refresh",
            "",
            f"- status: `{payload.get('status')}`",
            f"- total_rows: `{metrics.get('total_rows')}`",
            f"- planner_invoked_pct: `{metrics.get('planner_invoked_pct')}`",
            f"- deterministic_only_pct: `{metrics.get('deterministic_only_pct')}`",
            f"- stall_event_observed_count: `{metrics.get('stall_event_observed_count')}`",
            f"- success_after_branch_switch_count: `{metrics.get('success_after_branch_switch_count')}`",
            f"- success_without_branch_switch_evidence_pct: `{metrics.get('success_without_branch_switch_evidence_pct')}`",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh v0.3.8 branch-switch forcing candidates with live run results.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = refresh_branch_switch_candidates(
        candidate_taskset_path=str(args.candidate_taskset),
        results_path=str(args.results),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
