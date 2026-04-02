from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_same_branch_continuity_candidate_refresh_v0_3_10"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_same_branch_continuity_candidate_refresh_v0_3_10"


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


def _candidate_branch_rows(task: dict, result: dict) -> list[dict]:
    rows = result.get("candidate_next_branches")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    rows = result.get("candidate_branches")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    rows = task.get("candidate_next_branches")
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


def _state_signature(attempt: dict) -> tuple[object, ...]:
    params = tuple(_candidate_parameters(attempt))
    return (
        bool(attempt.get("check_model_pass")),
        bool(attempt.get("simulate_pass")),
        _norm(attempt.get("observed_failure_type")),
        _norm(attempt.get("reason")),
        params,
    )


def _derive_branch_sequence(*, task: dict, detail: dict) -> list[str]:
    branch_rows = _candidate_branch_rows(task, detail)
    branch_support = _branch_support_map(branch_rows)
    sequence: list[str] = []
    for attempt in _attempt_rows(detail):
        branch_id = _detect_branch_for_attempt(branch_support, attempt)
        if branch_id and (not sequence or sequence[-1] != branch_id):
            sequence.append(branch_id)
    return sequence


def _derive_same_branch_evidence(*, task: dict, result: dict, detail: dict) -> dict:
    success = _norm(result.get("verdict")).upper() == "PASS" or _norm(result.get("executor_status")).upper() == "PASS"
    branch_rows = _candidate_branch_rows(task, result)
    branch_support = _branch_support_map(branch_rows)
    selected_branch = _norm(result.get("selected_branch") or task.get("selected_branch"))
    current_branch = _norm(result.get("current_branch") or task.get("current_branch"))
    sequence = _derive_branch_sequence(task=task, detail=detail)
    branch_identity_continuous = bool(
        selected_branch
        and current_branch
        and selected_branch == current_branch
        and (not sequence or set(sequence) == {selected_branch})
    )

    refinement_events = []
    last_signature: tuple[object, ...] | None = None
    for attempt in _attempt_rows(detail):
        branch_id = _detect_branch_for_attempt(branch_support, attempt)
        if branch_id != selected_branch:
            continue
        params = _candidate_parameters(attempt)
        if not params:
            continue
        signature = _state_signature(attempt)
        if signature == last_signature:
            continue
        refinement_events.append(
            {
                "round": int(attempt.get("round") or 0),
                "branch_id": branch_id,
                "candidate_parameters": params,
                "state_signature": signature,
            }
        )
        last_signature = signature

    refinement_count = len(refinement_events)
    branch_switch_event_observed = bool(len(set(sequence)) > 1)
    success_after_same_branch_continuation = bool(
        success
        and branch_identity_continuous
        and not branch_switch_event_observed
        and refinement_count >= 2
    )
    success_without_branch_switch_evidence = bool(success and not branch_switch_event_observed)
    if success_after_same_branch_continuation:
        outcome_state = "multi_step_same_branch_success"
    elif success and branch_identity_continuous and not branch_switch_event_observed:
        outcome_state = "same_branch_one_shot_or_accidental_success"
    elif success:
        outcome_state = "hidden_branch_change_success"
    else:
        outcome_state = "stalled_unresolved_same_branch_failure"

    return {
        "candidate_next_branches": branch_rows,
        "detected_branch_sequence": sequence,
        "selected_branch": selected_branch or "",
        "current_branch": current_branch or "",
        "branch_identity_continuous": branch_identity_continuous,
        "same_branch_refinement_event_count": refinement_count,
        "same_branch_refinement_events": refinement_events,
        "previous_successful_same_branch_step": (
            f"round_{refinement_events[-1]['round']}" if refinement_events else ""
        ),
        "continuation_refinement_target": (
            refinement_events[-1]["candidate_parameters"][0] if refinement_events else ""
        ),
        "continuation_outcome_state": outcome_state,
        "branch_switch_event_observed": branch_switch_event_observed,
        "success_after_same_branch_continuation": success_after_same_branch_continuation,
        "success_with_explicit_branch_switch_evidence": bool(success and branch_switch_event_observed),
        "success_without_branch_switch_evidence": success_without_branch_switch_evidence,
    }


def refresh_same_branch_continuity_candidates(
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
    successful_case_count = 0
    continuity_success_count = 0
    switch_evidence_success_count = 0
    continuity_ge2_count = 0
    planner_event_case_count = 0
    repair_safety_blocked_case_count = 0
    rollback_applied_case_count = 0
    planner_experience_context_truncated_case_count = 0
    replan_context_truncated_case_count = 0

    frozen_mainline_task_ids = [_item_id(row) for row in tasks if _item_id(row)]

    for task in tasks:
        item_id = _item_id(task)
        result = dict(results_index.get(item_id, {}) or {})
        detail = _load_json(result.get("result_json_path") or task.get("result_json_path") or "")
        if result:
            matched_result_count += 1
        protocol = (
            result.get("baseline_measurement_protocol")
            if isinstance(result.get("baseline_measurement_protocol"), dict)
            else task.get("baseline_measurement_protocol")
        ) or top_protocol
        runtime_hygiene = _executor_runtime_hygiene(detail)
        evidence = _derive_same_branch_evidence(task=task, result=result, detail=detail)
        merged = {
            **task,
            "verdict": _norm(result.get("verdict") or task.get("verdict")),
            "executor_status": _norm(result.get("executor_status") or task.get("executor_status")),
            "planner_invoked": result.get("planner_invoked") if "planner_invoked" in result else task.get("planner_invoked"),
            "rounds_used": int(result.get("rounds_used") or task.get("rounds_used") or 0),
            "resolution_path": _norm(result.get("resolution_path") or task.get("resolution_path")),
            "llm_request_count": int(result.get("llm_request_count") or task.get("llm_request_count") or 0),
            "check_model_pass": result.get("check_model_pass") if "check_model_pass" in result else task.get("check_model_pass"),
            "simulate_pass": result.get("simulate_pass") if "simulate_pass" in result else task.get("simulate_pass"),
            "error_message": _norm(result.get("error_message") or task.get("error_message")),
            "result_json_path": _norm(result.get("result_json_path") or task.get("result_json_path")),
            "baseline_measurement_protocol": protocol,
            "executor_runtime_hygiene": runtime_hygiene,
            **evidence,
        }
        if merged.get("planner_invoked") is True:
            planner_invoked_count += 1
        if _norm(merged.get("resolution_path")) == "deterministic_rule_only":
            deterministic_only_count += 1
        if _norm(merged.get("verdict")).upper() == "PASS" or _norm(merged.get("executor_status")).upper() == "PASS":
            successful_case_count += 1
        if merged.get("success_after_same_branch_continuation") is True:
            continuity_success_count += 1
        if merged.get("success_with_explicit_branch_switch_evidence") is True:
            switch_evidence_success_count += 1
        if int(merged.get("same_branch_refinement_event_count") or 0) >= 2 and (
            _norm(merged.get("verdict")).upper() == "PASS" or _norm(merged.get("executor_status")).upper() == "PASS"
        ):
            continuity_ge2_count += 1
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
            "success_after_same_branch_continuation_count": continuity_success_count,
            "success_with_explicit_branch_switch_evidence_count": switch_evidence_success_count,
            "success_with_explicit_branch_switch_evidence_pct": round(100.0 * switch_evidence_success_count / total, 1) if total else 0.0,
            "same_branch_continuity_success_pct": round(100.0 * continuity_success_count / successful_case_count, 1) if successful_case_count else 0.0,
            "multi_step_same_branch_success_count_ge_2": continuity_ge2_count,
            "planner_event_case_count": planner_event_case_count,
            "repair_safety_blocked_case_count": repair_safety_blocked_case_count,
            "rollback_applied_case_count": rollback_applied_case_count,
            "planner_experience_context_truncated_case_count": planner_experience_context_truncated_case_count,
            "replan_context_truncated_case_count": replan_context_truncated_case_count,
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
            "# v0.3.10 Same-Branch Continuity Candidate Refresh",
            "",
            f"- status: `{payload.get('status')}`",
            f"- total_rows: `{metrics.get('total_rows')}`",
            f"- planner_invoked_pct: `{metrics.get('planner_invoked_pct')}`",
            f"- deterministic_only_pct: `{metrics.get('deterministic_only_pct')}`",
            f"- success_after_same_branch_continuation_count: `{metrics.get('success_after_same_branch_continuation_count')}`",
            f"- same_branch_continuity_success_pct: `{metrics.get('same_branch_continuity_success_pct')}`",
            f"- planner_event_case_count: `{metrics.get('planner_event_case_count')}`",
            f"- rollback_applied_case_count: `{metrics.get('rollback_applied_case_count')}`",
            f"- repair_safety_blocked_case_count: `{metrics.get('repair_safety_blocked_case_count')}`",
            f"- planner_experience_context_truncated_case_count: `{metrics.get('planner_experience_context_truncated_case_count')}`",
            f"- replan_context_truncated_case_count: `{metrics.get('replan_context_truncated_case_count')}`",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh v0.3.10 same-branch continuity candidates with live run results.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = refresh_same_branch_continuity_candidates(
        candidate_taskset_path=str(args.candidate_taskset),
        results_path=str(args.results),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
