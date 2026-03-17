from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_multi_round_baseline_summary_v1 import _executor_attempt_count, _ratio, _task_index, _write_json


SCHEMA_VERSION = "agent_modelica_behavioral_contract_baseline_summary_v1"
ALLOWED_FAIL_BUCKETS = {
    "steady_state_miss",
    "overshoot_or_settling_violation",
    "mode_transition_miss",
    "llm_patch_drift",
    "source_unstable",
    "infra",
}
FAILURE_TYPE_TO_BUCKET = {
    "steady_state_target_violation": "steady_state_miss",
    "transient_response_contract_violation": "overshoot_or_settling_violation",
    "mode_transition_contract_violation": "mode_transition_miss",
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


def _infer_fail_bucket(record: dict, task: dict) -> str:
    bucket = str(record.get("contract_fail_bucket") or record.get("failure_bucket") or "").strip().lower()
    if bucket in ALLOWED_FAIL_BUCKETS:
        return bucket
    failure_type = str(task.get("failure_type") or "").strip().lower()
    return FAILURE_TYPE_TO_BUCKET.get(failure_type, "infra")


def _contract_pass(record: dict) -> bool:
    if "contract_pass" in record:
        return bool(record.get("contract_pass"))
    hard_checks = record.get("hard_checks")
    if isinstance(hard_checks, dict) and "physics_contract_pass" in hard_checks:
        return bool(hard_checks.get("physics_contract_pass"))
    return bool(record.get("passed"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize behavioral contract baseline results")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_behavioral_contract_baseline_summary_v1/summary.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))
    task_map = _task_index(taskset)
    success_by_failure_type: dict[str, dict] = {}
    contract_fail_by_failure_type: dict[str, dict] = {}
    contract_fail_breakdown = {bucket: 0 for bucket in sorted(ALLOWED_FAIL_BUCKETS)}
    executor_attempt_values: list[float] = []
    contract_pass_count = 0

    for record in [row for row in (baseline_results.get("records") or []) if isinstance(row, dict)]:
        task_id = str(record.get("task_id") or "").strip()
        task = task_map.get(task_id, {})
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        success_row = success_by_failure_type.setdefault(failure_type, {"task_count": 0, "success_count": 0})
        fail_row = contract_fail_by_failure_type.setdefault(failure_type, {"task_count": 0, "contract_fail_count": 0})
        success_row["task_count"] += 1
        fail_row["task_count"] += 1
        executor_attempt_values.append(float(_executor_attempt_count(record)))
        if _contract_pass(record):
            contract_pass_count += 1
            if bool(record.get("passed")):
                success_row["success_count"] += 1
            continue
        fail_row["contract_fail_count"] += 1
        bucket = _infer_fail_bucket(record, task)
        contract_fail_breakdown[bucket] = int(contract_fail_breakdown.get(bucket, 0)) + 1

    total_tasks = int(challenge.get("total_tasks") or len(task_map))
    for row in success_by_failure_type.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    for row in contract_fail_by_failure_type.values():
        row["contract_fail_pct"] = _ratio(int(row.get("contract_fail_count") or 0), int(row.get("task_count") or 0))

    dominant_contract_fail_bucket = "none"
    if any(contract_fail_breakdown.values()):
        dominant_contract_fail_bucket = max(contract_fail_breakdown.items(), key=lambda item: (int(item[1]), item[0]))[0]
    contract_headroom_status = (
        "behavioral_headroom_present"
        if float(_ratio(total_tasks - contract_pass_count, total_tasks)) > 0.0
        else "task_construction_still_too_easy"
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": str(baseline_summary.get("status") or "FAIL"),
        "total_tasks": total_tasks,
        "success_count": int(baseline_summary.get("success_count") or 0),
        "success_at_k_pct": float(baseline_summary.get("success_at_k_pct") or 0.0),
        "contract_pass_count": contract_pass_count,
        "contract_pass_pct": _ratio(contract_pass_count, total_tasks),
        "contract_fail_count": max(0, total_tasks - contract_pass_count),
        "contract_fail_breakdown": contract_fail_breakdown,
        "contract_fail_breakdown_pct": {key: _ratio(int(value), total_tasks) for key, value in contract_fail_breakdown.items()},
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_contract_family": challenge.get("counts_by_contract_family") if isinstance(challenge.get("counts_by_contract_family"), dict) else {},
        "contract_metric_coverage": challenge.get("contract_metric_coverage") if isinstance(challenge.get("contract_metric_coverage"), dict) else {},
        "success_by_failure_type": success_by_failure_type,
        "contract_fail_by_failure_type": contract_fail_by_failure_type,
        "median_executor_attempts": round(_median(executor_attempt_values), 2),
        "dominant_contract_fail_bucket": dominant_contract_fail_bucket,
        "contract_headroom_status": contract_headroom_status,
        "sources": {
            "challenge_summary": args.challenge_summary,
            "baseline_summary": args.baseline_summary,
            "baseline_results": args.baseline_results,
        },
    }
    _write_json(args.out, summary)
    print(json.dumps({"status": summary.get("status"), "contract_pass_pct": summary.get("contract_pass_pct"), "contract_headroom_status": contract_headroom_status}))
    if str(summary.get("status")) == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
