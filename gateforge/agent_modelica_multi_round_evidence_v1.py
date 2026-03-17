from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_multi_round_evidence_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _task_index(taskset_payload: dict) -> dict[str, dict]:
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    return {str(task.get("task_id") or "").strip(): task for task in tasks if str(task.get("task_id") or "").strip()}


def _success_by_failure_type(taskset_payload: dict, results_payload: dict) -> dict[str, dict]:
    task_map = _task_index(taskset_payload)
    counts: dict[str, dict] = {}
    for record in [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]:
        task = task_map.get(str(record.get("task_id") or "").strip(), {})
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        row = counts.setdefault(failure_type, {"task_count": 0, "success_count": 0})
        row["task_count"] += 1
        if bool(record.get("passed")):
            row["success_count"] += 1
    for row in counts.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    return counts


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


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _result_medians(results_payload: dict) -> tuple[float, float]:
    attempt_values: list[float] = []
    time_values: list[float] = []
    for record in [row for row in (results_payload.get("records") or []) if isinstance(row, dict) and bool(row.get("passed"))]:
        attempt_values.append(float(_executor_attempt_count(record)))
        try:
            time_values.append(float(record.get("time_to_pass_sec") or 0.0))
        except Exception:
            pass
    return round(_median(attempt_values), 2), round(_median(time_values), 2)


def _decision_status(
    *,
    baseline_pct: float,
    deterministic_pct: float,
    retrieval_pct: float,
    first_round_pass_pct: float,
    median_repair_rounds: float,
) -> tuple[str, str, str, str]:
    if baseline_pct >= 100.0 and (first_round_pass_pct > 85.0 or median_repair_rounds < 2.0):
        return "not_observed", "not_observed", "hold", "task_construction_still_too_easy"
    if baseline_pct >= 100.0:
        return "not_observed", "not_observed", "needs_review", "baseline_already_saturated_but_nontrivial"
    deterministic_status = "observed" if deterministic_pct > baseline_pct else "not_observed"
    if retrieval_pct > max(baseline_pct, deterministic_pct):
        retrieval_status = "retrieval_uplift_observed"
    elif deterministic_status == "observed" and retrieval_pct >= deterministic_pct:
        retrieval_status = "retrieval_hold_the_floor"
    else:
        retrieval_status = "not_observed"
    if deterministic_status == "observed" or retrieval_status == "retrieval_uplift_observed":
        return retrieval_status, deterministic_status, "promote", "none"
    return retrieval_status, deterministic_status, "needs_review", "multi_round_headroom_present"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize multi-round evidence")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--deterministic-summary", required=True)
    parser.add_argument("--deterministic-results", required=True)
    parser.add_argument("--retrieval-summary", required=True)
    parser.add_argument("--retrieval-results", required=True)
    parser.add_argument("--retrieval-audit-summary", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_multi_round_failure_live_evidence_v1/evidence_summary.json")
    parser.add_argument("--gate-out", default="artifacts/agent_modelica_multi_round_failure_live_evidence_v1/gate_summary.json")
    parser.add_argument("--decision-out", default="artifacts/agent_modelica_multi_round_failure_live_evidence_v1/decision_summary.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    deterministic_summary = _load_json(args.deterministic_summary)
    deterministic_results = _load_json(args.deterministic_results)
    retrieval_summary = _load_json(args.retrieval_summary)
    retrieval_results = _load_json(args.retrieval_results)
    retrieval_audit = _load_json(args.retrieval_audit_summary)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))
    deterministic_executor_median_attempts, deterministic_median_time_to_pass_sec = _result_medians(deterministic_results)
    retrieval_executor_median_attempts, retrieval_median_time_to_pass_sec = _result_medians(retrieval_results)

    baseline_pct = float(baseline_summary.get("success_at_k_pct") or 0.0)
    deterministic_pct = float(deterministic_summary.get("success_at_k_pct") or baseline_pct)
    retrieval_pct = float(retrieval_summary.get("success_at_k_pct") or deterministic_pct)
    first_round_pass_pct = float(
        baseline_summary.get("executor_first_attempt_pass_pct")
        or baseline_summary.get("first_round_pass_pct")
        or 0.0
    )
    median_repair_rounds = float(
        baseline_summary.get("median_executor_attempts")
        or baseline_summary.get("median_repair_rounds")
        or 0.0
    )
    retrieval_uplift_status, deterministic_uplift_status, decision, primary_reason = _decision_status(
        baseline_pct=baseline_pct,
        deterministic_pct=deterministic_pct,
        retrieval_pct=retrieval_pct,
        first_round_pass_pct=first_round_pass_pct,
        median_repair_rounds=median_repair_rounds,
    )
    gate_status = "PASS" if decision == "promote" else ("NEEDS_REVIEW" if decision in {"needs_review", "hold"} else "FAIL")

    baseline_by_failure = _success_by_failure_type(taskset, baseline_results)
    deterministic_by_failure = _success_by_failure_type(taskset, deterministic_results)
    retrieval_by_failure = _success_by_failure_type(taskset, retrieval_results)
    success_by_failure_type: dict[str, dict] = {}
    for failure_type in sorted(set(baseline_by_failure.keys()) | set(deterministic_by_failure.keys()) | set(retrieval_by_failure.keys())):
        base = baseline_by_failure.get(failure_type, {})
        det = deterministic_by_failure.get(failure_type, {})
        ret = retrieval_by_failure.get(failure_type, {})
        success_by_failure_type[failure_type] = {
            "task_count": int(ret.get("task_count") or det.get("task_count") or base.get("task_count") or 0),
            "baseline_off_success_at_k_pct": float(base.get("success_at_k_pct") or 0.0),
            "deterministic_on_success_at_k_pct": float(det.get("success_at_k_pct") or 0.0),
            "retrieval_on_success_at_k_pct": float(ret.get("success_at_k_pct") or 0.0),
            "deterministic_delta_pp": round(float(det.get("success_at_k_pct") or 0.0) - float(base.get("success_at_k_pct") or 0.0), 2),
            "retrieval_delta_pp": round(float(ret.get("success_at_k_pct") or 0.0) - float(det.get("success_at_k_pct") or 0.0), 2),
            "retrieval_uplift_status": (
                "retrieval_uplift_observed"
                if float(ret.get("success_at_k_pct") or 0.0) > float(det.get("success_at_k_pct") or 0.0)
                else ("retrieval_hold_the_floor" if float(ret.get("success_at_k_pct") or 0.0) >= float(det.get("success_at_k_pct") or 0.0) and float(det.get("success_at_k_pct") or 0.0) > float(base.get("success_at_k_pct") or 0.0) else "not_observed")
            ),
        }

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_multi_round_family": challenge.get("counts_by_multi_round_family") if isinstance(challenge.get("counts_by_multi_round_family"), dict) else {},
        "counts_by_expected_rounds_min": challenge.get("counts_by_expected_rounds_min") if isinstance(challenge.get("counts_by_expected_rounds_min"), dict) else {},
        "cascade_depth_distribution": challenge.get("cascade_depth_distribution") if isinstance(challenge.get("cascade_depth_distribution"), dict) else {},
        "success_at_k": {
            "baseline_off_pct": baseline_pct,
            "deterministic_on_pct": deterministic_pct,
            "retrieval_on_pct": retrieval_pct,
            "deterministic_delta_pp": round(deterministic_pct - baseline_pct, 2),
            "retrieval_delta_pp": round(retrieval_pct - deterministic_pct, 2),
            "retrieval_vs_deterministic_delta_pp": round(retrieval_pct - deterministic_pct, 2),
        },
        "success_by_failure_type": success_by_failure_type,
        "round_histogram": baseline_summary.get("round_histogram") if isinstance(baseline_summary.get("round_histogram"), dict) else {},
        "executor_attempt_histogram": baseline_summary.get("executor_attempt_histogram") if isinstance(baseline_summary.get("executor_attempt_histogram"), dict) else {},
        "rounds_by_failure_type": baseline_summary.get("rounds_by_failure_type") if isinstance(baseline_summary.get("rounds_by_failure_type"), dict) else {},
        "first_round_pass_pct": first_round_pass_pct,
        "second_round_pass_pct": float(baseline_summary.get("second_round_pass_pct") or 0.0),
        "third_round_pass_pct": float(baseline_summary.get("third_round_pass_pct") or 0.0),
        "median_repair_rounds": median_repair_rounds,
        "executor_first_attempt_pass_pct": float(baseline_summary.get("executor_first_attempt_pass_pct") or 0.0),
        "executor_second_attempt_pass_pct": float(baseline_summary.get("executor_second_attempt_pass_pct") or 0.0),
        "executor_third_attempt_pass_pct": float(baseline_summary.get("executor_third_attempt_pass_pct") or 0.0),
        "median_executor_attempts": float(baseline_summary.get("median_executor_attempts") or 0.0),
        "deterministic_median_executor_attempts": deterministic_executor_median_attempts,
        "retrieval_median_executor_attempts": retrieval_executor_median_attempts,
        "retrieval_vs_deterministic_delta_pp": round(retrieval_pct - deterministic_pct, 2),
        "retrieval_executor_attempt_delta": round(retrieval_executor_median_attempts - deterministic_executor_median_attempts, 2),
        "deterministic_median_time_to_pass_sec": deterministic_median_time_to_pass_sec,
        "retrieval_median_time_to_pass_sec": retrieval_median_time_to_pass_sec,
        "retrieval_time_delta_sec": round(retrieval_median_time_to_pass_sec - deterministic_median_time_to_pass_sec, 2),
        "retrieval_coverage_pct": float(retrieval_audit.get("retrieval_coverage_pct") or 0.0),
        "match_signal_coverage_pct": float(retrieval_audit.get("match_signal_coverage_pct") or 0.0),
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": deterministic_uplift_status,
        "baseline_saturation_status": "saturated" if baseline_pct >= 100.0 else "headroom_remaining",
        "next_priority_gap_family": (
            "task_construction"
            if baseline_pct >= 100.0
            else ("retrieval policy" if deterministic_uplift_status == "observed" and retrieval_uplift_status != "retrieval_uplift_observed" else "deterministic repair policy")
        ),
    }
    gate = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "decision": decision,
        "primary_reason": primary_reason,
        "success_by_failure_type": success_by_failure_type,
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": deterministic_uplift_status,
        "retrieval_vs_deterministic_delta_pp": evidence["success_at_k"]["retrieval_vs_deterministic_delta_pp"],
        "retrieval_executor_attempt_delta": evidence["retrieval_executor_attempt_delta"],
        "retrieval_time_delta_sec": evidence["retrieval_time_delta_sec"],
        "baseline_saturation_status": evidence["baseline_saturation_status"],
        "retrieval_coverage_pct": evidence["retrieval_coverage_pct"],
        "executor_first_attempt_pass_pct": evidence["executor_first_attempt_pass_pct"],
        "median_executor_attempts": evidence["median_executor_attempts"],
    }
    decision_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "decision": decision,
        "primary_reason": primary_reason,
        "counts_by_library": evidence["counts_by_library"],
        "success_by_failure_type": success_by_failure_type,
        "baseline_vs_deterministic_by_failure_type": {k: {"baseline_off_success_at_k_pct": v["baseline_off_success_at_k_pct"], "deterministic_on_success_at_k_pct": v["deterministic_on_success_at_k_pct"], "delta_pp": v["deterministic_delta_pp"]} for k, v in success_by_failure_type.items()},
        "baseline_vs_retrieval_by_failure_type": {k: {"baseline_off_success_at_k_pct": v["baseline_off_success_at_k_pct"], "retrieval_on_success_at_k_pct": v["retrieval_on_success_at_k_pct"], "delta_pp": round(v["retrieval_on_success_at_k_pct"] - v["baseline_off_success_at_k_pct"], 2)} for k, v in success_by_failure_type.items()},
        "retrieval_vs_deterministic_by_failure_type": {k: {"deterministic_on_success_at_k_pct": v["deterministic_on_success_at_k_pct"], "retrieval_on_success_at_k_pct": v["retrieval_on_success_at_k_pct"], "delta_pp": v["retrieval_delta_pp"], "retrieval_uplift_status": v["retrieval_uplift_status"]} for k, v in success_by_failure_type.items()},
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": evidence["deterministic_uplift_status"],
        "retrieval_vs_deterministic_delta_pp": evidence["success_at_k"]["retrieval_vs_deterministic_delta_pp"],
        "retrieval_executor_attempt_delta": evidence["retrieval_executor_attempt_delta"],
        "retrieval_time_delta_sec": evidence["retrieval_time_delta_sec"],
        "baseline_saturation_status": evidence["baseline_saturation_status"],
        "retrieval_coverage_pct": evidence["retrieval_coverage_pct"],
        "executor_first_attempt_pass_pct": evidence["executor_first_attempt_pass_pct"],
        "median_executor_attempts": evidence["median_executor_attempts"],
        "next_priority_gap_family": evidence["next_priority_gap_family"],
    }
    _write_json(args.out, evidence)
    _write_json(args.gate_out, gate)
    _write_json(args.decision_out, decision_summary)
    print(json.dumps({"status": gate_status, "decision": decision, "primary_reason": primary_reason}))
    if gate_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
