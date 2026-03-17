from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_behavioral_contract_baseline_summary_v1 import _load_json
from .agent_modelica_multi_round_evidence_v1 import _median, _result_medians, _task_index, _write_json


SCHEMA_VERSION = "agent_modelica_behavioral_contract_evidence_v1"


def _result_contract_pass_by_failure_type(taskset_payload: dict, results_payload: dict) -> dict[str, dict]:
    task_map = _task_index(taskset_payload)
    counts: dict[str, dict] = {}
    for record in [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]:
        task = task_map.get(str(record.get("task_id") or "").strip(), {})
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        row = counts.setdefault(failure_type, {"task_count": 0, "contract_pass_count": 0})
        row["task_count"] += 1
        hard_checks = record.get("hard_checks") if isinstance(record.get("hard_checks"), dict) else {}
        contract_pass = record.get("contract_pass")
        if contract_pass is None and "physics_contract_pass" in hard_checks:
            contract_pass = hard_checks.get("physics_contract_pass")
        if bool(contract_pass if contract_pass is not None else record.get("passed")):
            row["contract_pass_count"] += 1
    for row in counts.values():
        total = int(row.get("task_count") or 0)
        row["contract_pass_pct"] = round((int(row.get("contract_pass_count") or 0) / total) * 100.0, 2) if total > 0 else 0.0
    return counts


def _hardest_contract_family(baseline_summary: dict, challenge: dict, taskset_payload: dict) -> str:
    family_counts = challenge.get("counts_by_contract_family") if isinstance(challenge.get("counts_by_contract_family"), dict) else {}
    if not family_counts:
        return "unknown"
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    by_family: dict[str, list[str]] = {}
    for task in tasks:
        family = str(task.get("contract_family") or "unknown").strip().lower()
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        by_family.setdefault(family, []).append(failure_type)
    contract_fail_by_failure_type = baseline_summary.get("contract_fail_by_failure_type") if isinstance(baseline_summary.get("contract_fail_by_failure_type"), dict) else {}
    family_scores: list[tuple[float, str]] = []
    for family, failure_types in by_family.items():
        fail_count = 0
        task_count = 0
        for failure_type in failure_types:
            row = contract_fail_by_failure_type.get(failure_type) if isinstance(contract_fail_by_failure_type.get(failure_type), dict) else {}
            fail_count += int(row.get("contract_fail_count") or 0)
            task_count += int(row.get("task_count") or 0)
        score = round((fail_count / task_count) * 100.0, 2) if task_count > 0 else 0.0
        family_scores.append((score, family))
    if not family_scores:
        return "unknown"
    family_scores.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return family_scores[0][1]


def _retrieval_status(*, baseline_pct: float, deterministic_pct: float, retrieval_pct: float, deterministic_attempts: float, retrieval_attempts: float) -> str:
    if retrieval_pct > max(baseline_pct, deterministic_pct):
        return "retrieval_uplift_observed"
    if retrieval_pct >= deterministic_pct and deterministic_pct > baseline_pct:
        if retrieval_attempts > 0.0 and deterministic_attempts > 0.0 and retrieval_attempts < deterministic_attempts:
            return "retrieval_uplift_observed"
        return "retrieval_hold_the_floor"
    return "not_observed"


def _decision_status(*, baseline_contract_pass_pct: float, deterministic_contract_pass_pct: float, retrieval_contract_pass_pct: float, baseline_fail_pct: float, deterministic_attempts: float, retrieval_attempts: float) -> tuple[str, str, str]:
    if baseline_contract_pass_pct >= 95.0 and baseline_fail_pct <= 5.0:
        return "behavioral_task_construction_too_easy", "not_observed", "hold"
    if baseline_fail_pct > 0.0 and deterministic_contract_pass_pct <= baseline_contract_pass_pct:
        return "behavioral_headroom_present", "not_observed", "needs_review"
    if deterministic_contract_pass_pct > baseline_contract_pass_pct:
        retrieval_status = _retrieval_status(
            baseline_pct=baseline_contract_pass_pct,
            deterministic_pct=deterministic_contract_pass_pct,
            retrieval_pct=retrieval_contract_pass_pct,
            deterministic_attempts=deterministic_attempts,
            retrieval_attempts=retrieval_attempts,
        )
        if retrieval_status == "retrieval_uplift_observed":
            return "retrieval_uplift_observed", "observed", "promote"
        if retrieval_status == "retrieval_hold_the_floor":
            return "retrieval_hold_the_floor", "observed", "promote"
        return "deterministic_uplift_observed", "observed", "promote"
    return "behavioral_headroom_present", "not_observed", "needs_review"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize behavioral contract evidence")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--deterministic-summary", required=True)
    parser.add_argument("--deterministic-results", required=True)
    parser.add_argument("--retrieval-summary", required=True)
    parser.add_argument("--retrieval-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_behavioral_contract_evidence_v1/evidence.json")
    parser.add_argument("--gate-out", default="artifacts/agent_modelica_behavioral_contract_evidence_v1/gate.json")
    parser.add_argument("--decision-out", default="artifacts/agent_modelica_behavioral_contract_evidence_v1/decision.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    deterministic_summary = _load_json(args.deterministic_summary)
    deterministic_results = _load_json(args.deterministic_results)
    retrieval_summary = _load_json(args.retrieval_summary)
    retrieval_results = _load_json(args.retrieval_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))

    baseline_pct = float(baseline_summary.get("contract_pass_pct") or 0.0)
    deterministic_pct = float(deterministic_summary.get("contract_pass_pct") or deterministic_summary.get("success_at_k_pct") or baseline_pct)
    retrieval_pct = float(retrieval_summary.get("contract_pass_pct") or retrieval_summary.get("success_at_k_pct") or deterministic_pct)
    baseline_fail_pct = round(max(0.0, 100.0 - baseline_pct), 2)
    deterministic_attempts, _ = _result_medians(deterministic_results)
    retrieval_attempts, _ = _result_medians(retrieval_results)
    primary_reason, deterministic_uplift_status, decision = _decision_status(
        baseline_contract_pass_pct=baseline_pct,
        deterministic_contract_pass_pct=deterministic_pct,
        retrieval_contract_pass_pct=retrieval_pct,
        baseline_fail_pct=baseline_fail_pct,
        deterministic_attempts=deterministic_attempts,
        retrieval_attempts=retrieval_attempts,
    )
    retrieval_uplift_status = _retrieval_status(
        baseline_pct=baseline_pct,
        deterministic_pct=deterministic_pct,
        retrieval_pct=retrieval_pct,
        deterministic_attempts=deterministic_attempts,
        retrieval_attempts=retrieval_attempts,
    )
    if primary_reason == "deterministic_uplift_observed":
        retrieval_uplift_status = "not_observed"
    hardest_contract_family = _hardest_contract_family(baseline_summary, challenge, taskset)
    baseline_by_failure = _result_contract_pass_by_failure_type(taskset, baseline_results)
    deterministic_by_failure = _result_contract_pass_by_failure_type(taskset, deterministic_results)
    retrieval_by_failure = _result_contract_pass_by_failure_type(taskset, retrieval_results)
    by_failure_type: dict[str, dict] = {}
    for failure_type in sorted(set(baseline_by_failure) | set(deterministic_by_failure) | set(retrieval_by_failure)):
        base = baseline_by_failure.get(failure_type, {})
        det = deterministic_by_failure.get(failure_type, {})
        ret = retrieval_by_failure.get(failure_type, {})
        by_failure_type[failure_type] = {
            "task_count": int(ret.get("task_count") or det.get("task_count") or base.get("task_count") or 0),
            "baseline_contract_pass_pct": float(base.get("contract_pass_pct") or 0.0),
            "deterministic_contract_pass_pct": float(det.get("contract_pass_pct") or 0.0),
            "retrieval_contract_pass_pct": float(ret.get("contract_pass_pct") or 0.0),
            "deterministic_delta_pp": round(float(det.get("contract_pass_pct") or 0.0) - float(base.get("contract_pass_pct") or 0.0), 2),
            "retrieval_delta_pp": round(float(ret.get("contract_pass_pct") or 0.0) - float(det.get("contract_pass_pct") or 0.0), 2),
        }

    retrieval_limit_status = (
        "retrieval_limit_reached"
        if deterministic_uplift_status == "observed" and retrieval_uplift_status != "retrieval_uplift_observed"
        else "headroom_remaining"
    )
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if decision == "promote" else "NEEDS_REVIEW",
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "counts_by_contract_family": challenge.get("counts_by_contract_family") if isinstance(challenge.get("counts_by_contract_family"), dict) else {},
        "contract_metric_coverage": challenge.get("contract_metric_coverage") if isinstance(challenge.get("contract_metric_coverage"), dict) else {},
        "contract_pass": {
            "baseline_pct": baseline_pct,
            "deterministic_pct": deterministic_pct,
            "retrieval_pct": retrieval_pct,
            "deterministic_delta_pp": round(deterministic_pct - baseline_pct, 2),
            "retrieval_vs_deterministic_delta_pp": round(retrieval_pct - deterministic_pct, 2),
        },
        "contract_fail_breakdown": baseline_summary.get("contract_fail_breakdown") if isinstance(baseline_summary.get("contract_fail_breakdown"), dict) else {},
        "median_executor_attempts": float(baseline_summary.get("median_executor_attempts") or 0.0),
        "deterministic_median_executor_attempts": deterministic_attempts,
        "retrieval_median_executor_attempts": retrieval_attempts,
        "hardest_contract_family": hardest_contract_family,
        "success_by_failure_type": by_failure_type,
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": deterministic_uplift_status,
        "retrieval_limit_status": retrieval_limit_status,
        "primary_reason": primary_reason,
    }
    gate = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": evidence["status"],
        "decision": decision,
        "primary_reason": primary_reason,
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": deterministic_uplift_status,
        "retrieval_limit_status": retrieval_limit_status,
        "hardest_contract_family": hardest_contract_family,
        "median_executor_attempts": evidence["median_executor_attempts"],
    }
    decision_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": evidence["status"],
        "decision": decision,
        "primary_reason": primary_reason,
        "hardest_contract_family": hardest_contract_family,
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": deterministic_uplift_status,
        "retrieval_limit_status": retrieval_limit_status,
        "contract_pass": evidence["contract_pass"],
        "success_by_failure_type": by_failure_type,
    }
    _write_json(args.out, evidence)
    _write_json(args.gate_out, gate)
    _write_json(args.decision_out, decision_summary)
    print(json.dumps({"status": evidence["status"], "decision": decision, "primary_reason": primary_reason}))


if __name__ == "__main__":
    main()
