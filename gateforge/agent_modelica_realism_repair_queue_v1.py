from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import canonical_error_type_v0, canonical_stage_from_failure_type_v0


SCHEMA_VERSION = "agent_modelica_realism_repair_queue_v1"
TASKS_SCHEMA_VERSION = "agent_modelica_realism_repair_queue_tasks_v1"
WAVE1_FAILURE_TYPES = {
    "underconstrained_system",
    "connector_mismatch",
    "initialization_infeasible",
}
REASON_PRIORITY = {
    "stage_truncation": 0,
    "manifestation_signal_gap": 1,
    "manifestation_stage_shift": 2,
    "subtype_signal_gap": 3,
    "repair_policy_gap": 4,
}
REASON_ACTIONS = {
    "stage_truncation": "strengthen initialization realism operators so failures manifest in simulate/init instead of check",
    "manifestation_signal_gap": "strengthen topology realism operators so underconstrained_system manifests as a structural failure before repair",
    "manifestation_stage_shift": "tighten underconstrained topology edits and structural diagnostics so failures surface during check/model-check instead of drifting into simulate",
    "subtype_signal_gap": "strengthen connector/port mismatch edits and subtype mapping so connector_mismatch is surfaced explicitly",
    "repair_policy_gap": "improve wave1 repair playbook and policy for structurally aligned failures instead of changing mutation operators",
}
REASON_LABELS = {
    "stage_truncation": "initialization failure is truncated at check stage",
    "manifestation_signal_gap": "declared realism task resolves without ever surfacing the intended failure signal",
    "manifestation_stage_shift": "underconstrained signal appears, but it surfaces in the wrong canonical type or stage",
    "subtype_signal_gap": "connector mismatch signal is too weak to surface the expected subtype",
    "repair_policy_gap": "repair policy fails despite aligned structural failure signal",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sorted_dict(payload: dict[str, object]) -> dict[str, object]:
    return {str(k): payload[k] for k in sorted(payload.keys())}


def _first_attempt(record: dict) -> dict:
    attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
    attempts = [x for x in attempts if isinstance(x, dict)]
    if not attempts:
        return {}
    return attempts[0]


def _attempt_observation(attempt: dict) -> tuple[str, str, str]:
    diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
    observed_failure_type = canonical_error_type_v0(
        str(attempt.get("observed_failure_type") or diagnostic.get("error_type") or "").strip().lower()
    )
    observed_stage = str(diagnostic.get("stage") or "").strip().lower()
    if not observed_stage:
        observed_stage = canonical_stage_from_failure_type_v0(observed_failure_type)
    observed_subtype = str(diagnostic.get("error_subtype") or "none").strip().lower() or "none"
    return observed_failure_type or "none", observed_stage or "none", observed_subtype


def _has_failure_signal(observed_failure_type: str, observed_stage: str, observed_subtype: str) -> bool:
    return (
        str(observed_failure_type or "").strip().lower() not in {"", "none"}
        or str(observed_stage or "").strip().lower() in {"check", "simulate"}
        or str(observed_subtype or "").strip().lower() not in {"", "none"}
    )


def _manifestation_attempt(record: dict) -> dict:
    attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
    attempts = [x for x in attempts if isinstance(x, dict)]
    for attempt in attempts:
        observed_failure_type, observed_stage, observed_subtype = _attempt_observation(attempt)
        if _has_failure_signal(observed_failure_type, observed_stage, observed_subtype):
            return attempt
    return {}


def _record_map(run_results: dict) -> dict[str, dict]:
    records = run_results.get("records") if isinstance(run_results.get("records"), list) else []
    out: dict[str, dict] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        if task_id:
            out[task_id] = row
    return out


def _reason_for_task(task: dict, record: dict, realism_summary: dict) -> str:
    failure_type = str(task.get("failure_type") or "").strip().lower()
    if failure_type not in WAVE1_FAILURE_TYPES:
        return ""

    manifestation_view = (
        realism_summary.get("failure_manifestation_view") if isinstance(realism_summary.get("failure_manifestation_view"), dict) else {}
    )
    by_failure_type = manifestation_view.get("by_failure_type") if isinstance(manifestation_view.get("by_failure_type"), dict) else {}
    if not by_failure_type:
        by_failure_type = realism_summary.get("by_failure_type") if isinstance(realism_summary.get("by_failure_type"), dict) else {}
    failure_row = by_failure_type.get(failure_type) if isinstance(by_failure_type.get(failure_type), dict) else {}
    mismatch_summary = manifestation_view.get("mismatch_summary") if isinstance(manifestation_view.get("mismatch_summary"), dict) else {}
    if not mismatch_summary:
        mismatch_summary = realism_summary.get("mismatch_summary") if isinstance(realism_summary.get("mismatch_summary"), dict) else {}
    attempt = _manifestation_attempt(record)
    observed_failure_type, observed_stage, observed_subtype = _attempt_observation(attempt or {})
    has_failure_signal = _has_failure_signal(observed_failure_type, observed_stage, observed_subtype)

    if failure_type == "initialization_infeasible":
        if int(mismatch_summary.get("initialization_truncated_by_check_count") or 0) > 0 and (
            observed_stage == "check" or observed_failure_type == "model_check_error"
        ):
            return "stage_truncation"
        return ""

    if failure_type == "connector_mismatch":
        canonical_ok = float(failure_row.get("canonical_match_rate_pct") or 0.0) >= 100.0
        stage_ok = float(failure_row.get("stage_match_rate_pct") or 0.0) >= 100.0
        subtype_expected = observed_subtype == "connector_mismatch"
        if canonical_ok and stage_ok and not subtype_expected:
            return "subtype_signal_gap"
        return ""

    if failure_type == "underconstrained_system":
        if not has_failure_signal:
            return "manifestation_signal_gap"
        canonical_ok = float(failure_row.get("canonical_match_rate_pct") or 0.0) >= 100.0
        stage_ok = float(failure_row.get("stage_match_rate_pct") or 0.0) >= 100.0
        if not canonical_ok or not stage_ok:
            return "manifestation_stage_shift"
        l5_success_count_on = int(failure_row.get("l5_success_count_on") or 0)
        if canonical_ok and stage_ok and l5_success_count_on == 0:
            return "repair_policy_gap"
        return ""

    return ""


def _priority_sort_key(row: dict) -> tuple[int, int, str, str]:
    reason = str(row.get("priority_reason") or "")
    failure_type = str(row.get("failure_type") or "")
    rank = int(REASON_PRIORITY.get(reason, 999))
    if failure_type == "initialization_infeasible" and reason == "stage_truncation":
        rank = -1
    return (
        rank,
        -int(row.get("affected_task_count") or 0),
        failure_type,
        str(row.get("mutation_operator_family") or ""),
    )


def _resolve_run_root(out_dir: str, run_id: str = "", run_root: str = "") -> Path:
    if run_root:
        return Path(run_root)
    if run_id:
        return Path(out_dir) / "runs" / run_id
    latest = _load_json(Path(out_dir) / "latest_run.json")
    latest_root = str(latest.get("run_root") or "")
    return Path(latest_root) if latest_root else Path(out_dir)


def build_repair_queue_v1(*, run_root: str, update_final_summary: bool = True) -> dict:
    root = Path(run_root)
    final_summary_path = root / "final_run_summary.json"
    realism_summary_path = root / "realism_internal_summary.json"
    taskset_path = root / "challenge" / "taskset_frozen.json"
    l3_run_results_path = root / "main_l5" / "l3" / "run2" / "run_results.json"
    l3_quality_summary_path = root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json"
    out_summary_path = root / "repair_queue_summary.json"
    out_tasks_path = root / "repair_queue_tasks.json"
    out_md_path = root / "repair_queue_summary.md"

    final_summary = _load_json(final_summary_path)
    realism_summary = _load_json(realism_summary_path)
    taskset_payload = _load_json(taskset_path)
    l3_run_results = _load_json(l3_run_results_path)
    l3_quality_summary = _load_json(l3_quality_summary_path)

    reasons: list[str] = []
    status = "PASS"
    if not final_summary:
        status = "BLOCKED"
        reasons.append("final_run_summary_missing")
    if final_summary and (
        str(final_summary.get("status") or "").upper() == "BLOCKED"
        or str(final_summary.get("primary_reason") or "").strip() in {"live_request_budget_exceeded", "rate_limited"}
    ):
        status = "BLOCKED"
        reasons.append("final_run_blocked")
    if not realism_summary:
        status = "BLOCKED"
        reasons.append("realism_summary_missing")
    if not taskset_payload:
        status = "BLOCKED"
        reasons.append("taskset_missing")
    if not l3_run_results:
        status = "BLOCKED"
        reasons.append("l3_run_results_missing")
    if not l3_quality_summary:
        status = "BLOCKED"
        reasons.append("l3_quality_summary_missing")

    task_queue: list[dict] = []
    priorities: list[dict] = []
    by_failure_type: dict[str, dict] = {}
    by_operator_family: dict[str, dict] = {}

    if status != "BLOCKED":
        task_map = {
            str(task.get("task_id") or ""): task
            for task in (taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else [])
            if isinstance(task, dict) and str(task.get("task_id") or "").strip()
        }
        record_map = _record_map(l3_run_results)

        for task_id, task in sorted(task_map.items()):
            failure_type = str(task.get("failure_type") or "").strip().lower()
            if failure_type not in WAVE1_FAILURE_TYPES:
                continue
            record = record_map.get(task_id) if isinstance(record_map.get(task_id), dict) else {}
            if not record:
                continue
            attempt = _manifestation_attempt(record)
            observed_failure_type, observed_stage, observed_subtype = _attempt_observation(attempt or {})

            priority_reason = _reason_for_task(task, record, realism_summary)
            if not priority_reason:
                continue

            recommended_action = REASON_ACTIONS[priority_reason]
            queue_row = {
                "task_id": task_id,
                "origin_task_id": str(task.get("origin_task_id") or ""),
                "failure_type": failure_type,
                "category": str(task.get("category") or ""),
                "mutation_operator": str(task.get("mutation_operator") or ""),
                "mutation_operator_family": str(task.get("mutation_operator_family") or ""),
                "source_model_path": str(task.get("source_model_path") or ""),
                "mutated_model_path": str(task.get("mutated_model_path") or ""),
                "expected_stage": str(task.get("expected_stage") or ""),
                "observed_stage": observed_stage,
                "observed_failure_type": observed_failure_type,
                "observed_subtype": observed_subtype,
                "priority_reason": priority_reason,
                "priority_reason_label": REASON_LABELS[priority_reason],
                "recommended_action": recommended_action,
                "mutated_objects": task.get("mutated_objects") if isinstance(task.get("mutated_objects"), list) else [],
            }
            task_queue.append(queue_row)

        grouped: dict[tuple[str, str], dict] = {}
        operator_grouped: dict[str, dict] = {}
        for row in task_queue:
            key = (str(row["failure_type"]), str(row["priority_reason"]))
            group = grouped.setdefault(
                key,
                {
                    "failure_type": row["failure_type"],
                    "category": row["category"],
                    "mutation_operator_family": row["mutation_operator_family"],
                    "priority_reason": row["priority_reason"],
                    "priority_reason_label": row["priority_reason_label"],
                    "recommended_action": row["recommended_action"],
                    "affected_task_count": 0,
                    "task_ids": [],
                    "origin_task_ids": [],
                },
            )
            group["affected_task_count"] = int(group.get("affected_task_count", 0)) + 1
            group["task_ids"].append(row["task_id"])
            group["origin_task_ids"].append(row["origin_task_id"])

            family = str(row["mutation_operator_family"] or "")
            op_group = operator_grouped.setdefault(
                family,
                {
                    "mutation_operator_family": family,
                    "affected_task_count": 0,
                    "failure_types": {},
                    "priority_reasons": {},
                },
            )
            op_group["affected_task_count"] = int(op_group.get("affected_task_count", 0)) + 1
            op_group["failure_types"][str(row["failure_type"])] = int(op_group["failure_types"].get(str(row["failure_type"]), 0)) + 1
            op_group["priority_reasons"][str(row["priority_reason"])] = int(op_group["priority_reasons"].get(str(row["priority_reason"]), 0)) + 1

        priorities = sorted(grouped.values(), key=_priority_sort_key)
        task_queue = sorted(
            task_queue,
            key=lambda row: (
                _priority_sort_key(
                    {
                        "priority_reason": row["priority_reason"],
                        "affected_task_count": 1,
                        "failure_type": row["failure_type"],
                        "mutation_operator_family": row["mutation_operator_family"],
                    }
                ),
                str(row["task_id"]),
            ),
        )

        for row in priorities:
            failure_type = str(row["failure_type"])
            by_failure_type[failure_type] = {
                "priority_reason": row["priority_reason"],
                "priority_reason_label": row["priority_reason_label"],
                "recommended_action": row["recommended_action"],
                "affected_task_count": int(row["affected_task_count"]),
                "category": row["category"],
                "mutation_operator_family": row["mutation_operator_family"],
                "task_ids": sorted(set(str(x) for x in row["task_ids"] if str(x))),
                "origin_task_ids": sorted(set(str(x) for x in row["origin_task_ids"] if str(x))),
            }

        for family, row in operator_grouped.items():
            top_reason = ""
            top_rank = 999
            for reason in row["priority_reasons"].keys():
                rank = int(REASON_PRIORITY.get(reason, 999))
                if rank < top_rank:
                    top_rank = rank
                    top_reason = str(reason)
            by_operator_family[family] = {
                "affected_task_count": int(row["affected_task_count"]),
                "failure_types": _sorted_dict({str(k): int(v) for k, v in row["failure_types"].items()}),
                "priority_reasons": _sorted_dict({str(k): int(v) for k, v in row["priority_reasons"].items()}),
                "top_priority_reason": top_reason,
            }

    top_priority = priorities[0] if priorities else {}
    top_priority_reason = str(top_priority.get("priority_reason") or "none")
    top_repair_priority = ""
    if top_priority:
        top_repair_priority = f"{top_priority.get('failure_type')}:{top_priority_reason}"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": status,
        "run_id": str(final_summary.get("run_id") or root.name),
        "run_root": str(root),
        "top_priority_reason": top_priority_reason,
        "top_repair_priority": top_repair_priority,
        "recommended_next_action": str(top_priority.get("recommended_action") or ("none" if status != "BLOCKED" else "")),
        "priorities": priorities,
        "by_failure_type": _sorted_dict(by_failure_type),
        "by_operator_family": _sorted_dict(by_operator_family),
        "task_queue": task_queue,
        "task_queue_count": len(task_queue),
        "reasons": sorted(set(reasons)),
        "inputs": {
            "final_run_summary": str(final_summary_path),
            "realism_internal_summary": str(realism_summary_path),
            "taskset": str(taskset_path),
            "l3_run_results": str(l3_run_results_path),
            "l3_quality_summary": str(l3_quality_summary_path),
        },
    }
    tasks_payload = {
        "schema_version": TASKS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "run_id": str(final_summary.get("run_id") or root.name),
        "run_root": str(root),
        "tasks": task_queue,
    }
    _write_json(out_summary_path, summary)
    _write_json(out_tasks_path, tasks_payload)
    _write_md(
        out_md_path,
        [
            "# Agent Modelica Realism Repair Queue v1",
            "",
            f"- status: `{summary.get('status')}`",
            f"- top_repair_priority: `{summary.get('top_repair_priority')}`",
            f"- top_priority_reason: `{summary.get('top_priority_reason')}`",
            f"- recommended_next_action: `{summary.get('recommended_next_action')}`",
            f"- task_queue_count: `{summary.get('task_queue_count')}`",
            f"- reasons: `{summary.get('reasons')}`",
            "",
        ],
    )

    if update_final_summary and final_summary:
        final_summary["repair_queue_status"] = summary.get("status")
        final_summary["repair_queue_path"] = str(out_summary_path)
        final_summary["top_repair_priority"] = top_repair_priority
        paths = final_summary.get("paths") if isinstance(final_summary.get("paths"), dict) else {}
        paths["repair_queue_summary"] = str(out_summary_path)
        paths["repair_queue_tasks"] = str(out_tasks_path)
        final_summary["paths"] = paths
        _write_json(final_summary_path, final_summary)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave1 repair queue from finalized realism evidence")
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_l4_realism_evidence_v1")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-root", default="")
    parser.add_argument("--update-final-summary", default="1")
    args = parser.parse_args()

    run_root = _resolve_run_root(args.out_dir, run_id=args.run_id, run_root=args.run_root)
    payload = build_repair_queue_v1(run_root=str(run_root), update_final_summary=str(args.update_final_summary).strip() not in {"0", "false", "False"})
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
