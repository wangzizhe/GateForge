from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_wave2_1_evidence_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
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


def _decision_status(baseline_pct: float, deterministic_pct: float, retrieval_pct: float) -> tuple[str, str]:
    if retrieval_pct > deterministic_pct:
        return "retrieval_uplift_observed", "promote"
    if deterministic_pct > baseline_pct:
        return "deterministic_uplift_observed", "promote"
    if baseline_pct >= 100.0:
        return "baseline_already_saturated", "promote"
    return "coverage_high_uplift_zero", "needs_review"


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize wave2.1 harder-dynamics evidence")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--deterministic-summary", required=True)
    parser.add_argument("--deterministic-results", required=True)
    parser.add_argument("--retrieval-summary", required=True)
    parser.add_argument("--retrieval-results", required=True)
    parser.add_argument("--retrieval-audit-summary", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_wave2_1_harder_dynamics_live_evidence_v1/evidence_summary.json")
    parser.add_argument("--gate-out", default="artifacts/agent_modelica_wave2_1_harder_dynamics_live_evidence_v1/gate_summary.json")
    parser.add_argument("--decision-out", default="artifacts/agent_modelica_wave2_1_harder_dynamics_live_evidence_v1/decision_summary.json")
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

    baseline_pct = float(baseline_summary.get("success_at_k_pct") or 0.0)
    deterministic_pct = float(deterministic_summary.get("success_at_k_pct") or 0.0)
    retrieval_pct = float(retrieval_summary.get("success_at_k_pct") or 0.0)
    uplift_status, decision = _decision_status(baseline_pct, deterministic_pct, retrieval_pct)
    gate_status = "PASS" if decision == "promote" else "NEEDS_REVIEW"
    primary_reason = "none" if decision == "promote" else "uplift_not_observed"

    baseline_by_failure = _success_by_failure_type(taskset, baseline_results)
    deterministic_by_failure = _success_by_failure_type(taskset, deterministic_results)
    retrieval_by_failure = _success_by_failure_type(taskset, retrieval_results)
    success_by_failure_type: dict[str, dict] = {}
    for failure_type in sorted(set(baseline_by_failure.keys()) | set(deterministic_by_failure.keys()) | set(retrieval_by_failure.keys())):
        base_row = baseline_by_failure.get(failure_type, {})
        det_row = deterministic_by_failure.get(failure_type, {})
        ret_row = retrieval_by_failure.get(failure_type, {})
        success_by_failure_type[failure_type] = {
            "task_count": int(ret_row.get("task_count") or det_row.get("task_count") or base_row.get("task_count") or 0),
            "baseline_off_success_at_k_pct": float(base_row.get("success_at_k_pct") or 0.0),
            "deterministic_on_success_at_k_pct": float(det_row.get("success_at_k_pct") or 0.0),
            "retrieval_on_success_at_k_pct": float(ret_row.get("success_at_k_pct") or 0.0),
            "deterministic_delta_pp": round(float(det_row.get("success_at_k_pct") or 0.0) - float(base_row.get("success_at_k_pct") or 0.0), 2),
            "retrieval_delta_pp": round(float(ret_row.get("success_at_k_pct") or 0.0) - float(det_row.get("success_at_k_pct") or 0.0), 2),
        }
    next_priority_gap_family = "none"
    if uplift_status == "coverage_high_uplift_zero":
        hardest = sorted(success_by_failure_type.items(), key=lambda item: (item[1]["retrieval_on_success_at_k_pct"], item[0]))
        if hardest:
            hardest_type = hardest[0][0]
            if hardest_type == "solver_sensitive_simulate_failure":
                next_priority_gap_family = "simulate stabilization"
            elif hardest_type == "event_logic_error":
                next_priority_gap_family = "deterministic repair policy"
            else:
                next_priority_gap_family = "component semantics"

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "counts_by_failure_type": challenge.get("counts_by_failure_type") if isinstance(challenge.get("counts_by_failure_type"), dict) else {},
        "success_at_k": {
            "baseline_off_pct": baseline_pct,
            "deterministic_on_pct": deterministic_pct,
            "retrieval_on_pct": retrieval_pct,
            "deterministic_delta_pp": round(deterministic_pct - baseline_pct, 2),
            "retrieval_delta_pp": round(retrieval_pct - deterministic_pct, 2),
        },
        "success_by_failure_type": success_by_failure_type,
        "failure_breakdown_by_failure_type": baseline_summary.get("failure_breakdown_by_failure_type") if isinstance(baseline_summary.get("failure_breakdown_by_failure_type"), dict) else {},
        "diagnostic_parse_coverage_by_failure_type": baseline_summary.get("diagnostic_parse_coverage_by_failure_type") if isinstance(baseline_summary.get("diagnostic_parse_coverage_by_failure_type"), dict) else {},
        "retrieval_coverage_pct": float(retrieval_audit.get("retrieval_coverage_pct") or 0.0),
        "match_signal_coverage_pct": float(retrieval_audit.get("match_signal_coverage_pct") or 0.0),
        "retrieval_uplift_status": uplift_status,
        "deterministic_uplift_status": "observed" if deterministic_pct > baseline_pct else "not_observed",
        "baseline_saturation_status": "saturated" if baseline_pct >= 100.0 else "headroom_remaining",
        "next_priority_gap_family": next_priority_gap_family,
    }
    gate = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "decision": decision,
        "primary_reason": primary_reason,
        "success_by_failure_type": success_by_failure_type,
        "retrieval_uplift_status": uplift_status,
        "baseline_saturation_status": evidence["baseline_saturation_status"],
        "retrieval_coverage_pct": evidence["retrieval_coverage_pct"],
    }
    decision_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "decision": decision,
        "primary_reason": primary_reason,
        "counts_by_library": evidence.get("counts_by_library"),
        "success_by_failure_type": success_by_failure_type,
        "baseline_vs_deterministic_by_failure_type": {k: {"baseline_off_success_at_k_pct": v["baseline_off_success_at_k_pct"], "deterministic_on_success_at_k_pct": v["deterministic_on_success_at_k_pct"], "delta_pp": v["deterministic_delta_pp"]} for k, v in success_by_failure_type.items()},
        "baseline_vs_retrieval_by_failure_type": {k: {"baseline_off_success_at_k_pct": v["baseline_off_success_at_k_pct"], "retrieval_on_success_at_k_pct": v["retrieval_on_success_at_k_pct"], "delta_pp": round(v["retrieval_on_success_at_k_pct"] - v["baseline_off_success_at_k_pct"], 2)} for k, v in success_by_failure_type.items()},
        "retrieval_uplift_status": uplift_status,
        "deterministic_uplift_status": evidence["deterministic_uplift_status"],
        "baseline_saturation_status": evidence["baseline_saturation_status"],
        "retrieval_coverage_pct": evidence["retrieval_coverage_pct"],
        "next_priority_gap_family": next_priority_gap_family,
    }
    _write_json(args.out, evidence)
    _write_json(args.gate_out, gate)
    _write_json(args.decision_out, decision_summary)
    print(json.dumps({"status": gate_status, "decision": decision, "primary_reason": primary_reason}))
    if gate_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
