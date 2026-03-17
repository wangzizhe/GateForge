from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_multi_round_baseline_summary_v1"


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


def _executor_attempt_count(record: dict) -> int:
    attempts = record.get("attempts")
    if isinstance(attempts, list) and attempts:
        outer = [row for row in attempts if isinstance(row, dict)]
        nested_max = 0
        for row in outer:
            nested = row.get("attempts")
            if isinstance(nested, list):
                nested_max = max(nested_max, len([item for item in nested if isinstance(item, dict)]))
            stdout_tail = row.get("executor_stdout_tail")
            if isinstance(stdout_tail, str) and stdout_tail.strip().startswith("{"):
                try:
                    payload = json.loads(stdout_tail)
                except Exception:
                    payload = {}
                nested_payload = payload.get("attempts")
                if isinstance(nested_payload, list):
                    nested_max = max(nested_max, len([item for item in nested_payload if isinstance(item, dict)]))
        if nested_max > 0:
            return nested_max
        return max(1, len(outer))
    try:
        return max(1, int(record.get("rounds_used") or 1))
    except Exception:
        return 1


def _record_buckets(taskset_payload: dict, results_payload: dict) -> tuple[dict[str, dict], dict[str, dict], dict[str, int], int, int, int, list[str], dict[str, int], int, int, int, list[str], list[int]]:
    task_map = _task_index(taskset_payload)
    success_by_failure_type: dict[str, dict] = {}
    rounds_by_failure_type: dict[str, dict] = {}
    round_histogram = {"1": 0, "2": 0, "3_plus": 0}
    first_round_pass = 0
    second_round_pass = 0
    third_round_pass = 0
    first_round_pass_task_ids: list[str] = []
    executor_attempt_histogram = {"1": 0, "2": 0, "3_plus": 0}
    executor_first_attempt_pass = 0
    executor_second_attempt_pass = 0
    executor_third_attempt_pass = 0
    executor_first_attempt_pass_task_ids: list[str] = []
    executor_attempt_values: list[int] = []
    for record in [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]:
        task_id = str(record.get("task_id") or "").strip()
        task = task_map.get(task_id, {})
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        success_row = success_by_failure_type.setdefault(failure_type, {"task_count": 0, "success_count": 0})
        round_row = rounds_by_failure_type.setdefault(
            failure_type,
            {
                "task_count": 0,
                "first_round_pass_count": 0,
                "second_round_pass_count": 0,
                "third_round_or_more_pass_count": 0,
                "executor_first_attempt_pass_count": 0,
                "executor_second_attempt_pass_count": 0,
                "executor_third_attempt_or_more_pass_count": 0,
            },
        )
        success_row["task_count"] += 1
        round_row["task_count"] += 1
        if not bool(record.get("passed")):
            continue
        success_row["success_count"] += 1
        rounds = int(record.get("rounds_used") or 0)
        if rounds <= 1:
            first_round_pass += 1
            round_row["first_round_pass_count"] += 1
            round_histogram["1"] += 1
            first_round_pass_task_ids.append(task_id)
        elif rounds == 2:
            second_round_pass += 1
            round_row["second_round_pass_count"] += 1
            round_histogram["2"] += 1
        else:
            third_round_pass += 1
            round_row["third_round_or_more_pass_count"] += 1
            round_histogram["3_plus"] += 1
        executor_attempts = _executor_attempt_count(record)
        executor_attempt_values.append(executor_attempts)
        if executor_attempts <= 1:
            executor_first_attempt_pass += 1
            round_row["executor_first_attempt_pass_count"] += 1
            executor_attempt_histogram["1"] += 1
            executor_first_attempt_pass_task_ids.append(task_id)
        elif executor_attempts == 2:
            executor_second_attempt_pass += 1
            round_row["executor_second_attempt_pass_count"] += 1
            executor_attempt_histogram["2"] += 1
        else:
            executor_third_attempt_pass += 1
            round_row["executor_third_attempt_or_more_pass_count"] += 1
            executor_attempt_histogram["3_plus"] += 1
    for row in success_by_failure_type.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    for row in rounds_by_failure_type.values():
        total = int(row.get("task_count") or 0)
        row["first_round_pass_pct"] = _ratio(int(row.get("first_round_pass_count") or 0), total)
        row["second_round_pass_pct"] = _ratio(int(row.get("second_round_pass_count") or 0), total)
        row["third_round_or_more_pass_pct"] = _ratio(int(row.get("third_round_or_more_pass_count") or 0), total)
        row["executor_first_attempt_pass_pct"] = _ratio(int(row.get("executor_first_attempt_pass_count") or 0), total)
        row["executor_second_attempt_pass_pct"] = _ratio(int(row.get("executor_second_attempt_pass_count") or 0), total)
        row["executor_third_attempt_or_more_pass_pct"] = _ratio(int(row.get("executor_third_attempt_or_more_pass_count") or 0), total)
    return (
        success_by_failure_type,
        rounds_by_failure_type,
        round_histogram,
        first_round_pass,
        second_round_pass,
        third_round_pass,
        first_round_pass_task_ids,
        executor_attempt_histogram,
        executor_first_attempt_pass,
        executor_second_attempt_pass,
        executor_third_attempt_pass,
        executor_first_attempt_pass_task_ids,
        executor_attempt_values,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize multi-round baseline results")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_multi_round_failure_live_evidence_v1/multi_round_baseline_summary.json")
    args = parser.parse_args()
    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))
    (
        success_by_failure_type,
        rounds_by_failure_type,
        round_histogram,
        first_round_pass,
        second_round_pass,
        third_round_pass,
        first_round_pass_task_ids,
        executor_attempt_histogram,
        executor_first_attempt_pass,
        executor_second_attempt_pass,
        executor_third_attempt_pass,
        executor_first_attempt_pass_task_ids,
        executor_attempt_values,
    ) = _record_buckets(taskset, baseline_results)
    total_tasks = int(challenge.get("total_tasks") or 0)
    executor_median_attempts = 0.0
    if executor_attempt_values:
        ordered = sorted(executor_attempt_values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            executor_median_attempts = float(ordered[mid])
        else:
            executor_median_attempts = float((ordered[mid - 1] + ordered[mid]) / 2.0)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": str(baseline_summary.get("status") or "FAIL"),
        "total_tasks": total_tasks,
        "success_count": int(baseline_summary.get("success_count") or 0),
        "success_at_k_pct": float(baseline_summary.get("success_at_k_pct") or 0.0),
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_multi_round_family": challenge.get("counts_by_multi_round_family") if isinstance(challenge.get("counts_by_multi_round_family"), dict) else {},
        "counts_by_expected_rounds_min": challenge.get("counts_by_expected_rounds_min") if isinstance(challenge.get("counts_by_expected_rounds_min"), dict) else {},
        "cascade_depth_distribution": challenge.get("cascade_depth_distribution") if isinstance(challenge.get("cascade_depth_distribution"), dict) else {},
        "success_by_failure_type": success_by_failure_type,
        "rounds_by_failure_type": rounds_by_failure_type,
        "round_histogram": round_histogram,
        "first_round_pass_count": first_round_pass,
        "first_round_pass_task_ids": first_round_pass_task_ids,
        "second_round_pass_count": second_round_pass,
        "third_round_pass_count": third_round_pass,
        "first_round_pass_pct": _ratio(first_round_pass, total_tasks),
        "second_round_pass_pct": _ratio(second_round_pass, total_tasks),
        "third_round_pass_pct": _ratio(third_round_pass, total_tasks),
        "median_repair_rounds": float(baseline_summary.get("median_repair_rounds") or 0.0),
        "executor_attempt_histogram": executor_attempt_histogram,
        "executor_first_attempt_pass_count": executor_first_attempt_pass,
        "executor_first_attempt_pass_task_ids": executor_first_attempt_pass_task_ids,
        "executor_second_attempt_pass_count": executor_second_attempt_pass,
        "executor_third_attempt_pass_count": executor_third_attempt_pass,
        "executor_first_attempt_pass_pct": _ratio(executor_first_attempt_pass, total_tasks),
        "executor_second_attempt_pass_pct": _ratio(executor_second_attempt_pass, total_tasks),
        "executor_third_attempt_pass_pct": _ratio(executor_third_attempt_pass, total_tasks),
        "median_executor_attempts": executor_median_attempts,
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
