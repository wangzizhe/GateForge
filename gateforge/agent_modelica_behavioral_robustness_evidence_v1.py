from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .agent_modelica_behavioral_robustness_baseline_summary_v1 import _load_json
from .agent_modelica_behavioral_contract_evidence_v1 import _result_contract_pass_by_failure_type
from .agent_modelica_multi_round_evidence_v1 import _result_medians, _task_index, _write_json


SCHEMA_VERSION = "agent_modelica_behavioral_robustness_evidence_v1"


def _hardest_robustness_family(baseline_summary: dict, taskset_payload: dict) -> str:
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    if not tasks:
        return "unknown"
    by_family: dict[str, list[str]] = {}
    for task in tasks:
        family = str(task.get("robustness_family") or "unknown").strip().lower()
        failure_type = str(task.get("failure_type") or "unknown").strip().lower()
        by_family.setdefault(family, []).append(failure_type)
    scenario_fail_by_failure_type = baseline_summary.get("scenario_fail_by_failure_type") if isinstance(baseline_summary.get("scenario_fail_by_failure_type"), dict) else {}
    scores: list[tuple[float, str]] = []
    for family, failure_types in by_family.items():
        fail_count = 0
        task_count = 0
        for failure_type in failure_types:
            row = scenario_fail_by_failure_type.get(failure_type) if isinstance(scenario_fail_by_failure_type.get(failure_type), dict) else {}
            fail_count += int(row.get("scenario_fail_count") or 0)
            task_count += int(row.get("task_count") or 0)
        score = round((fail_count / task_count) * 100.0, 2) if task_count > 0 else 0.0
        scores.append((score, family))
    scores.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scores[0][1] if scores else "unknown"


def _retrieval_status(*, baseline_pct: float, deterministic_pct: float, retrieval_pct: float, deterministic_attempts: float, retrieval_attempts: float) -> str:
    if retrieval_pct > max(baseline_pct, deterministic_pct):
        return "retrieval_uplift_observed"
    if retrieval_pct >= deterministic_pct and deterministic_pct > baseline_pct:
        if retrieval_attempts > 0.0 and deterministic_attempts > 0.0 and retrieval_attempts < deterministic_attempts:
            return "retrieval_uplift_observed"
        return "retrieval_hold_the_floor"
    return "not_observed"


def _decision_status(*, baseline_pass_pct: float, deterministic_pass_pct: float, retrieval_pass_pct: float, baseline_fail_pct: float, deterministic_attempts: float, retrieval_attempts: float) -> tuple[str, str, str]:
    if baseline_pass_pct >= 95.0 and baseline_fail_pct <= 5.0:
        return "robustness_task_construction_too_easy", "not_observed", "hold"
    if baseline_fail_pct > 0.0 and deterministic_pass_pct <= baseline_pass_pct:
        return "robustness_headroom_present", "not_observed", "needs_review"
    if deterministic_pass_pct > baseline_pass_pct:
        retrieval_status = _retrieval_status(
            baseline_pct=baseline_pass_pct,
            deterministic_pct=deterministic_pass_pct,
            retrieval_pct=retrieval_pass_pct,
            deterministic_attempts=deterministic_attempts,
            retrieval_attempts=retrieval_attempts,
        )
        if retrieval_status == "retrieval_uplift_observed":
            return "retrieval_uplift_observed", "observed", "promote"
        if retrieval_status == "retrieval_hold_the_floor":
            return "retrieval_hold_the_floor", "observed", "promote"
        return "deterministic_uplift_observed", "observed", "promote"
    return "robustness_headroom_present", "not_observed", "needs_review"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize behavioral robustness evidence")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--deterministic-summary", required=True)
    parser.add_argument("--deterministic-results", required=True)
    parser.add_argument("--retrieval-summary", required=True)
    parser.add_argument("--retrieval-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_behavioral_robustness_evidence_v1/evidence.json")
    parser.add_argument("--gate-out", default="artifacts/agent_modelica_behavioral_robustness_evidence_v1/gate.json")
    parser.add_argument("--decision-out", default="artifacts/agent_modelica_behavioral_robustness_evidence_v1/decision.json")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    deterministic_summary = _load_json(args.deterministic_summary)
    deterministic_results = _load_json(args.deterministic_results)
    retrieval_summary = _load_json(args.retrieval_summary)
    retrieval_results = _load_json(args.retrieval_results)
    taskset = _load_json(str(challenge.get("taskset_frozen_path") or ""))

    baseline_pct = float(baseline_summary.get("all_scenarios_pass_pct") or 0.0)
    deterministic_pct = float(deterministic_summary.get("all_scenarios_pass_pct") or deterministic_summary.get("contract_pass_pct") or deterministic_summary.get("success_at_k_pct") or baseline_pct)
    retrieval_pct = float(retrieval_summary.get("all_scenarios_pass_pct") or retrieval_summary.get("contract_pass_pct") or retrieval_summary.get("success_at_k_pct") or deterministic_pct)
    baseline_fail_pct = round(max(0.0, 100.0 - baseline_pct), 2)
    deterministic_attempts, _ = _result_medians(deterministic_results)
    retrieval_attempts, _ = _result_medians(retrieval_results)
    primary_reason, deterministic_uplift_status, decision = _decision_status(
        baseline_pass_pct=baseline_pct,
        deterministic_pass_pct=deterministic_pct,
        retrieval_pass_pct=retrieval_pct,
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
    hardest_robustness_family = _hardest_robustness_family(baseline_summary, taskset)
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
            "baseline_all_scenarios_pass_pct": float(base.get("contract_pass_pct") or 0.0),
            "deterministic_all_scenarios_pass_pct": float(det.get("contract_pass_pct") or 0.0),
            "retrieval_all_scenarios_pass_pct": float(ret.get("contract_pass_pct") or 0.0),
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
        "counts_by_robustness_family": challenge.get("counts_by_robustness_family") if isinstance(challenge.get("counts_by_robustness_family"), dict) else {},
        "scenario_count_distribution": challenge.get("scenario_count_distribution") if isinstance(challenge.get("scenario_count_distribution"), dict) else {},
        "all_scenarios_pass": {
            "baseline_pct": baseline_pct,
            "deterministic_pct": deterministic_pct,
            "retrieval_pct": retrieval_pct,
            "deterministic_delta_pp": round(deterministic_pct - baseline_pct, 2),
            "retrieval_vs_deterministic_delta_pp": round(retrieval_pct - deterministic_pct, 2),
        },
        "partial_pass_pct": float(baseline_summary.get("partial_pass_pct") or 0.0),
        "scenario_fail_breakdown": baseline_summary.get("scenario_fail_breakdown") if isinstance(baseline_summary.get("scenario_fail_breakdown"), dict) else {},
        "median_executor_attempts": float(baseline_summary.get("median_executor_attempts") or 0.0),
        "deterministic_median_executor_attempts": deterministic_attempts,
        "retrieval_median_executor_attempts": retrieval_attempts,
        "hardest_robustness_family": hardest_robustness_family,
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
        "hardest_robustness_family": hardest_robustness_family,
        "median_executor_attempts": evidence["median_executor_attempts"],
    }
    decision_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": evidence["status"],
        "decision": decision,
        "primary_reason": primary_reason,
        "hardest_robustness_family": hardest_robustness_family,
        "retrieval_uplift_status": retrieval_uplift_status,
        "deterministic_uplift_status": deterministic_uplift_status,
        "retrieval_limit_status": retrieval_limit_status,
        "all_scenarios_pass": evidence["all_scenarios_pass"],
        "success_by_failure_type": by_failure_type,
    }
    _write_json(args.out, evidence)
    _write_json(args.gate_out, gate)
    _write_json(args.decision_out, decision_summary)
    print(json.dumps({"status": evidence["status"], "decision": decision, "primary_reason": primary_reason}))


if __name__ == "__main__":
    main()
