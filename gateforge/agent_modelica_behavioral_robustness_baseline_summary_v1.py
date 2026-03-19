from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_multi_round_baseline_summary_v1 import _executor_attempt_count, _ratio, _task_index, _write_json


SCHEMA_VERSION = "agent_modelica_behavioral_robustness_baseline_summary_v1"
ALLOWED_FAIL_BUCKETS = {
    "single_case_only",
    "param_sensitivity_miss",
    "initial_condition_miss",
    "scenario_switch_miss",
    "llm_patch_drift",
    "infra",
}
FAILURE_TYPE_TO_BUCKET = {
    "param_perturbation_robustness_violation": "param_sensitivity_miss",
    "initial_condition_robustness_violation": "initial_condition_miss",
    "scenario_switch_robustness_violation": "scenario_switch_miss",
}


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _scenario_results(record: dict) -> list[dict]:
    rows = record.get("scenario_results")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _all_scenarios_pass(record: dict) -> bool:
    rows = _scenario_results(record)
    if rows:
        return all(bool(row.get("pass")) for row in rows)
    return bool(record.get("contract_pass"))


def _partial_pass(record: dict) -> bool:
    rows = _scenario_results(record)
    if not rows:
        return False
    passes = [bool(row.get("pass")) for row in rows]
    return any(passes) and not all(passes)


def _infer_fail_bucket(record: dict, task: dict) -> str:
    if _partial_pass(record):
        return "single_case_only"
    bucket = str(record.get("contract_fail_bucket") or record.get("failure_bucket") or "").strip().lower()
    if bucket in ALLOWED_FAIL_BUCKETS:
        return bucket
    failure_type = str(task.get("failure_type") or "").strip().lower()
    return FAILURE_TYPE_TO_BUCKET.get(failure_type, "infra")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize behavioral robustness baseline results")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_behavioral_robustness_baseline_summary_v1/summary.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))
    task_map = _task_index(taskset)
    success_by_failure_type: dict[str, dict] = {}
    scenario_fail_by_failure_type: dict[str, dict] = {}
    scenario_fail_breakdown = {bucket: 0 for bucket in sorted(ALLOWED_FAIL_BUCKETS)}
    executor_attempt_values: list[float] = []
    all_scenarios_pass_count = 0
    partial_pass_count = 0

    for record in [row for row in (baseline_results.get("records") or []) if isinstance(row, dict)]:
        task_id = str(record.get("task_id") or "").strip()
        task = task_map.get(task_id, {})
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        success_row = success_by_failure_type.setdefault(failure_type, {"task_count": 0, "success_count": 0})
        fail_row = scenario_fail_by_failure_type.setdefault(failure_type, {"task_count": 0, "scenario_fail_count": 0})
        success_row["task_count"] += 1
        fail_row["task_count"] += 1
        executor_attempt_values.append(float(_executor_attempt_count(record)))
        if _all_scenarios_pass(record):
            all_scenarios_pass_count += 1
            if bool(record.get("passed")):
                success_row["success_count"] += 1
            continue
        if _partial_pass(record):
            partial_pass_count += 1
        fail_row["scenario_fail_count"] += 1
        bucket = _infer_fail_bucket(record, task)
        scenario_fail_breakdown[bucket] = int(scenario_fail_breakdown.get(bucket, 0)) + 1

    total_tasks = int(challenge.get("total_tasks") or len(task_map))
    for row in success_by_failure_type.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    for row in scenario_fail_by_failure_type.values():
        row["scenario_fail_pct"] = _ratio(int(row.get("scenario_fail_count") or 0), int(row.get("task_count") or 0))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": str(baseline_summary.get("status") or "FAIL"),
        "total_tasks": total_tasks,
        "success_count": int(baseline_summary.get("success_count") or 0),
        "success_at_k_pct": float(baseline_summary.get("success_at_k_pct") or 0.0),
        "all_scenarios_pass_count": all_scenarios_pass_count,
        "all_scenarios_pass_pct": _ratio(all_scenarios_pass_count, total_tasks),
        "partial_pass_count": partial_pass_count,
        "partial_pass_pct": _ratio(partial_pass_count, total_tasks),
        "scenario_fail_count": max(0, total_tasks - all_scenarios_pass_count),
        "scenario_fail_breakdown": scenario_fail_breakdown,
        "success_by_failure_type": success_by_failure_type,
        "scenario_fail_by_failure_type": scenario_fail_by_failure_type,
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_robustness_family": challenge.get("counts_by_robustness_family") if isinstance(challenge.get("counts_by_robustness_family"), dict) else {},
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "scenario_count_distribution": challenge.get("scenario_count_distribution") if isinstance(challenge.get("scenario_count_distribution"), dict) else {},
        "median_executor_attempts": round(_median(executor_attempt_values), 2),
        "robustness_headroom_status": "robustness_headroom_present" if partial_pass_count > 0 or (total_tasks - all_scenarios_pass_count) > 0 else "task_construction_still_too_easy",
        "sources": {
            "challenge_summary": args.challenge_summary,
            "baseline_summary": args.baseline_summary,
            "baseline_results": args.baseline_results,
        },
    }
    _write_json(args.out, summary)
    print(json.dumps({"status": summary.get("status"), "all_scenarios_pass_pct": summary.get("all_scenarios_pass_pct"), "robustness_headroom_status": summary.get("robustness_headroom_status")}))
    if str(summary.get("status")) == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
