from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_wave2_2_baseline_summary_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _task_index(taskset_payload: dict) -> dict[str, dict]:
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    return {str(task.get("task_id") or "").strip(): task for task in tasks if str(task.get("task_id") or "").strip()}


def _record_buckets(taskset_payload: dict, results_payload: dict) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, dict], int, list[str], int]:
    task_map = _task_index(taskset_payload)
    success_by_failure_type: dict[str, dict] = {}
    failure_breakdown_by_failure_type: dict[str, dict] = {}
    diagnostic_parse_coverage_by_failure_type: dict[str, dict] = {}
    success_by_coupling_span: dict[str, dict] = {}
    trivial_restore_suspected_count = 0
    trivial_restore_suspected_task_ids: list[str] = []
    t0_failure_suspected_count = 0
    for record in [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]:
        task = task_map.get(str(record.get("task_id") or "").strip(), {})
        task_id = str(record.get("task_id") or "").strip()
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        coupling_span = str(task.get("coupling_span") or "unknown").strip().lower()
        success_row = success_by_failure_type.setdefault(failure_type, {"task_count": 0, "success_count": 0})
        success_row["task_count"] += 1
        coupling_row = success_by_coupling_span.setdefault(coupling_span, {"task_count": 0, "success_count": 0})
        coupling_row["task_count"] += 1
        if bool(record.get("passed")):
            success_row["success_count"] += 1
            coupling_row["success_count"] += 1
        parse_row = diagnostic_parse_coverage_by_failure_type.setdefault(failure_type, {"task_count": 0, "diagnostic_parse_count": 0})
        parse_row["task_count"] += 1
        audit = record.get("repair_audit") if isinstance(record.get("repair_audit"), dict) else {}
        attempts = [row for row in (record.get("attempts") or []) if isinstance(row, dict)]
        if str(audit.get("diagnostic_error_type") or "").strip() or any(str((attempt.get("diagnostic_ir") or {}).get("error_type") or "").strip() for attempt in attempts if isinstance(attempt.get("diagnostic_ir"), dict)):
            parse_row["diagnostic_parse_count"] += 1
        if bool(record.get("passed")) and int(record.get("rounds_used") or 0) <= 1 and (
            str(task.get("repair_triviality_risk") or "").strip().lower() in {"high", "medium"}
            or not bool(task.get("trivial_restore_guard"))
        ):
            trivial_restore_suspected_count += 1
            trivial_restore_suspected_task_ids.append(task_id)
        if any(
            "during initialization" in str(attempt.get("stderr_snippet") or "").lower()
            or "time 0.000000" in str(attempt.get("stderr_snippet") or "").lower()
            for attempt in attempts
        ):
            t0_failure_suspected_count += 1
        fail_row = failure_breakdown_by_failure_type.setdefault(
            failure_type,
            {
                "task_count": 0,
                "diagnostic_parse_fail": 0,
                "deterministic_repair_missing": 0,
                "llm_patch_drift": 0,
                "source_unstable": 0,
                "infra": 0,
                "task_too_easy": 0,
            },
        )
        fail_row["task_count"] += 1
        if bool(record.get("passed")):
            continue
        err = str(record.get("error_message") or "").strip().lower()
        if "docker" in err or "permission denied" in err or "rate_limited" in err or "live_executor_timeout" in err:
            fail_row["infra"] += 1
        elif "source_unstable" in err:
            fail_row["source_unstable"] += 1
        elif "drift" in err:
            fail_row["llm_patch_drift"] += 1
        elif "parse" in err or not str(audit.get("diagnostic_error_type") or "").strip():
            fail_row["diagnostic_parse_fail"] += 1
        else:
            fail_row["deterministic_repair_missing"] += 1
    for bucket in success_by_failure_type.values():
        bucket["success_at_k_pct"] = _ratio(int(bucket.get("success_count") or 0), int(bucket.get("task_count") or 0))
    for bucket in success_by_coupling_span.values():
        bucket["success_at_k_pct"] = _ratio(int(bucket.get("success_count") or 0), int(bucket.get("task_count") or 0))
    for bucket in diagnostic_parse_coverage_by_failure_type.values():
        bucket["diagnostic_parse_coverage_pct"] = _ratio(int(bucket.get("diagnostic_parse_count") or 0), int(bucket.get("task_count") or 0))
    return success_by_failure_type, failure_breakdown_by_failure_type, diagnostic_parse_coverage_by_failure_type, success_by_coupling_span, trivial_restore_suspected_count, trivial_restore_suspected_task_ids, t0_failure_suspected_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize wave2.2 coupled-hard baseline results")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_wave2_2_coupled_hard_live_evidence_v1/wave2_2_baseline_summary.json")
    args = parser.parse_args()
    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))
    success_by_failure_type, failure_breakdown_by_failure_type, diagnostic_parse_coverage_by_failure_type, success_by_coupling_span, trivial_restore_suspected_count, trivial_restore_suspected_task_ids, t0_failure_suspected_count = _record_buckets(taskset, baseline_results)
    total_tasks = int(challenge.get("total_tasks") or 0)
    first_round_pass_count = len(
        [
            row for row in (baseline_results.get("records") or [])
            if isinstance(row, dict) and bool(row.get("passed")) and int(row.get("rounds_used") or 0) <= 1
        ]
    )
    source_dependency_backed_count = len(
        [
            task for task in (taskset.get("tasks") or [])
            if isinstance(task, dict) and int(task.get("source_dependency_count") or 0) >= 2
        ]
    )
    delayed_failure_signal_count = len(
        [
            task for task in (taskset.get("tasks") or [])
            if isinstance(task, dict) and bool(task.get("delayed_failure_signal"))
        ]
    )
    hardest = sorted(success_by_failure_type.items(), key=lambda item: (float(item[1].get("success_at_k_pct") or 0.0), item[0]))[0][0] if success_by_failure_type else "none"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": str(baseline_summary.get("status") or "FAIL"),
        "total_tasks": total_tasks,
        "success_count": int(baseline_summary.get("success_count") or 0),
        "success_at_k_pct": float(baseline_summary.get("success_at_k_pct") or 0.0),
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_coupling_span": challenge.get("counts_by_coupling_span") if isinstance(challenge.get("counts_by_coupling_span"), dict) else {},
        "diagnostic_expectation_by_failure_type": challenge.get("diagnostic_expectation_by_failure_type") if isinstance(challenge.get("diagnostic_expectation_by_failure_type"), dict) else {},
        "success_by_failure_type": success_by_failure_type,
        "failure_breakdown_by_failure_type": failure_breakdown_by_failure_type,
        "diagnostic_parse_coverage_by_failure_type": diagnostic_parse_coverage_by_failure_type,
        "success_by_coupling_span": success_by_coupling_span,
        "trivial_restore_suspected_count": trivial_restore_suspected_count,
        "trivial_restore_suspected_pct": _ratio(trivial_restore_suspected_count, total_tasks),
        "trivial_restore_suspected_task_ids": trivial_restore_suspected_task_ids,
        "first_round_pass_pct": _ratio(first_round_pass_count, total_tasks),
        "t0_failure_suspected_count": t0_failure_suspected_count,
        "source_dependency_backed_task_pct": _ratio(source_dependency_backed_count, total_tasks),
        "delayed_failure_signal_pct": _ratio(delayed_failure_signal_count, total_tasks),
        "hardest_failure_type": hardest,
        "sources": {
            "challenge_summary": args.challenge_summary,
            "baseline_summary": args.baseline_summary,
            "baseline_results": args.baseline_results,
        },
    }
    _write_json(args.out, summary)
    print(json.dumps({"status": summary.get("status"), "success_count": summary.get("success_count"), "total_tasks": summary.get("total_tasks")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
