from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_unknown_library_evidence_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Unknown Library Evidence v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- primary_reason: `{payload.get('primary_reason')}`",
        f"- retrieval_coverage_pct: `{payload.get('retrieval_coverage_pct')}`",
        f"- non_regression_status: `{payload.get('non_regression_status')}`",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _record_failure_breakdown(results_payload: dict) -> dict:
    records = [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]
    model_fix_fail_count = 0
    retrieval_miss_count = 0
    infra_failure_count = 0
    for row in records:
        audit = row.get("repair_audit") if isinstance(row.get("repair_audit"), dict) else {}
        retrieved_count = int(audit.get("retrieved_example_count", 0) or 0)
        diagnostic_error_type = str(audit.get("diagnostic_error_type") or "").strip().lower()
        passed = bool(row.get("passed"))
        if retrieved_count <= 0:
            retrieval_miss_count += 1
        if not passed and retrieved_count > 0:
            model_fix_fail_count += 1
        if diagnostic_error_type in {"executor_runtime_error", "executor_invocation_error"}:
            infra_failure_count += 1
    return {
        "model_fix_fail_count": model_fix_fail_count,
        "retrieval_miss_count": retrieval_miss_count,
        "infra_failure_count": infra_failure_count,
    }


def _decision_for_library(library_row: dict) -> str:
    match_cov = float(library_row.get("match_signal_coverage_pct", 0.0) or 0.0)
    fallback_ratio = float(library_row.get("fallback_ratio_pct", 0.0) or 0.0)
    if match_cov >= 50.0 and fallback_ratio < 50.0:
        return "transferability_signal"
    return "generic_fallback_dominant"


def _load_taskset_from_challenge(challenge_payload: dict) -> dict:
    taskset_path = str(challenge_payload.get("taskset_frozen_path") or "").strip()
    if not taskset_path:
        return {}
    return _load_json(taskset_path)


def _task_index(taskset_payload: dict) -> dict[str, dict]:
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    return {str(task.get("task_id") or "").strip(): task for task in tasks if str(task.get("task_id") or "").strip()}


def _model_key(task: dict) -> str:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    for value in (
        source_meta.get("qualified_model_name"),
        task.get("model_hint"),
        source_meta.get("model_path"),
        task.get("source_model_path"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _detect_source_unstable_models(taskset_payload: dict, *results_payloads: dict) -> dict:
    task_map = _task_index(taskset_payload)
    model_rows: dict[str, dict] = {}
    task_ids: set[str] = set()
    for results_payload in results_payloads:
        records = [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]
        for record in records:
            if bool(record.get("passed")):
                continue
            attempts = [row for row in (record.get("attempts") or []) if isinstance(row, dict)]
            if not attempts:
                continue
            last_attempt = attempts[-1]
            last_reason = " ".join(
                [
                    str(last_attempt.get("reason") or ""),
                    str(last_attempt.get("error_message") or ""),
                    str(record.get("error_message") or ""),
                    str(record.get("simulate_error_message") or ""),
                ]
            ).lower()
            final_init_fail = str(last_attempt.get("observed_failure_type") or "").strip().lower() == "simulate_error" and "initialization failed" in last_reason
            source_repair_applied = any(
                bool(((attempt.get("source_repair") if isinstance(attempt.get("source_repair"), dict) else {}).get("applied")))
                for attempt in attempts
            )
            init_marker_applied = any(
                bool(((attempt.get("initialization_marker_repair") if isinstance(attempt.get("initialization_marker_repair"), dict) else {}).get("applied")))
                for attempt in attempts
            )
            if not final_init_fail or not (source_repair_applied or init_marker_applied):
                continue
            task_id = str(record.get("task_id") or "").strip()
            task = task_map.get(task_id, {})
            model_key = _model_key(task)
            if not model_key:
                continue
            source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
            row = model_rows.setdefault(
                model_key,
                {
                    "qualified_model_name": str(source_meta.get("qualified_model_name") or model_key),
                    "model_id": str(source_meta.get("model_id") or "").strip(),
                    "library_id": str(source_meta.get("library_id") or task.get("source_library") or "unknown").strip().lower(),
                    "task_ids": [],
                    "reasons": [],
                },
            )
            row["task_ids"].append(task_id)
            if source_repair_applied:
                row["reasons"].append("source_repair_applied_then_source_initialization_failed")
            if init_marker_applied:
                row["reasons"].append("initialization_marker_removed_then_source_initialization_failed")
            task_ids.add(task_id)

    counts_by_library: dict[str, int] = {}
    for row in model_rows.values():
        row["task_ids"] = sorted(set([item for item in row.get("task_ids") or [] if str(item).strip()]))
        row["reasons"] = sorted(set([item for item in row.get("reasons") or [] if str(item).strip()]))
        library_id = str(row.get("library_id") or "unknown").strip().lower()
        counts_by_library[library_id] = int(counts_by_library.get(library_id) or 0) + 1

    return {
        "model_count": len(model_rows),
        "task_count": len(task_ids),
        "qualified_model_names": sorted(model_rows.keys()),
        "model_ids": sorted(set([str(row.get("model_id") or "").strip() for row in model_rows.values() if str(row.get("model_id") or "").strip()])),
        "library_ids": sorted(set([str(row.get("library_id") or "").strip() for row in model_rows.values() if str(row.get("library_id") or "").strip()])),
        "counts_by_library": counts_by_library,
        "models": {key: value for key, value in sorted(model_rows.items())},
        "task_ids": sorted(task_ids),
    }


def _success_by_library(taskset_payload: dict, results_payload: dict, excluded_model_keys: set[str] | None = None) -> dict[str, dict]:
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    records = [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]
    task_to_library: dict[str, str] = {}
    excluded = set([str(item or "").strip() for item in (excluded_model_keys or set()) if str(item or "").strip()])
    for task in tasks:
        if _model_key(task) in excluded:
            continue
        source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
        task_id = str(task.get("task_id") or "").strip()
        library_id = str(source_meta.get("library_id") or task.get("source_library") or "unknown").strip().lower()
        if task_id:
            task_to_library[task_id] = library_id

    counts: dict[str, dict] = {}
    for record in records:
        task_id = str(record.get("task_id") or "").strip()
        library_id = task_to_library.get(task_id, "unknown")
        row = counts.setdefault(library_id, {"task_count": 0, "success_count": 0})
        row["task_count"] = int(row.get("task_count") or 0) + 1
        if bool(record.get("passed")):
            row["success_count"] = int(row.get("success_count") or 0) + 1
    for row in counts.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate unknown-library evidence, engineering gate, and decision summaries")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-off-summary", required=True)
    parser.add_argument("--baseline-off-results", required=True)
    parser.add_argument("--retrieval-on-summary", required=True)
    parser.add_argument("--retrieval-on-results", required=True)
    parser.add_argument("--retrieval-summary", required=True)
    parser.add_argument("--min-retrieval-on-success-at-k-pct", type=float, default=1.0)
    parser.add_argument("--min-retrieval-coverage-pct", type=float, default=50.0)
    parser.add_argument("--min-diagnostic-parse-coverage-pct", type=float, default=95.0)
    parser.add_argument("--out", default="artifacts/agent_modelica_unknown_library_evidence_v1/evidence_summary.json")
    parser.add_argument("--gate-out", default="artifacts/agent_modelica_unknown_library_evidence_v1/gate_summary.json")
    parser.add_argument("--decision-out", default="artifacts/agent_modelica_unknown_library_evidence_v1/decision_summary.json")
    parser.add_argument("--source-unstable-exclusions-out", default="")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_off_summary = _load_json(args.baseline_off_summary)
    baseline_off_results = _load_json(args.baseline_off_results)
    retrieval_on_summary = _load_json(args.retrieval_on_summary)
    retrieval_on_results = _load_json(args.retrieval_on_results)
    retrieval_summary = _load_json(args.retrieval_summary)
    taskset_payload = _load_taskset_from_challenge(challenge)

    required_payloads = {
        "challenge_summary": challenge,
        "baseline_off_summary": baseline_off_summary,
        "baseline_off_results": baseline_off_results,
        "retrieval_on_summary": retrieval_on_summary,
        "retrieval_on_results": retrieval_on_results,
        "retrieval_summary": retrieval_summary,
    }
    missing = [name for name, payload in required_payloads.items() if not payload]
    total_tasks = int(challenge.get("total_tasks") or 0)
    provenance_completeness = float(challenge.get("provenance_completeness_pct", 0.0) or 0.0)
    counts_by_library = challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {}

    off_success = float(baseline_off_summary.get("success_at_k_pct", 0.0) or 0.0)
    on_success = float(retrieval_on_summary.get("success_at_k_pct", 0.0) or 0.0)
    success_delta = round(on_success - off_success, 2)
    non_regression_status = "PASS" if success_delta >= 0.0 else "FAIL"

    retrieval_coverage = float(retrieval_summary.get("retrieval_coverage_pct", 0.0) or 0.0)
    match_signal_coverage = float(retrieval_summary.get("match_signal_coverage_pct", 0.0) or 0.0)
    diagnostic_parse_coverage = float(retrieval_summary.get("diagnostic_parse_coverage_pct", 0.0) or 0.0)
    failure_breakdown = _record_failure_breakdown(retrieval_on_results)
    provenance_incomplete_count = max(0, total_tasks - int(round((provenance_completeness / 100.0) * total_tasks)))
    source_unstable = _detect_source_unstable_models(taskset_payload, baseline_off_results, retrieval_on_results)
    excluded_model_keys = set(source_unstable.get("qualified_model_names") or [])
    success_by_library_off = _success_by_library(taskset_payload, baseline_off_results)
    success_by_library_on = _success_by_library(taskset_payload, retrieval_on_results)
    success_by_library_off_adjusted = _success_by_library(taskset_payload, baseline_off_results, excluded_model_keys=excluded_model_keys)
    success_by_library_on_adjusted = _success_by_library(taskset_payload, retrieval_on_results, excluded_model_keys=excluded_model_keys)
    success_by_library: dict[str, dict] = {}
    for library_id in sorted(set(success_by_library_off.keys()) | set(success_by_library_on.keys()) | set(counts_by_library.keys())):
        off_row = success_by_library_off.get(library_id, {})
        on_row = success_by_library_on.get(library_id, {})
        baseline_pct = float(off_row.get("success_at_k_pct", 0.0) or 0.0)
        retrieval_pct = float(on_row.get("success_at_k_pct", 0.0) or 0.0)
        success_by_library[library_id] = {
            "task_count": int(on_row.get("task_count") or off_row.get("task_count") or counts_by_library.get(library_id) or 0),
            "baseline_off_success_at_k_pct": baseline_pct,
            "retrieval_on_success_at_k_pct": retrieval_pct,
            "delta_pp": round(retrieval_pct - baseline_pct, 2),
        }
    adjusted_task_total = max(0, total_tasks - int(source_unstable.get("task_count") or 0))
    adjusted_off_success_count = sum(int(row.get("success_count") or 0) for row in success_by_library_off_adjusted.values())
    adjusted_on_success_count = sum(int(row.get("success_count") or 0) for row in success_by_library_on_adjusted.values())
    adjusted_off_success = _ratio(adjusted_off_success_count, adjusted_task_total)
    adjusted_on_success = _ratio(adjusted_on_success_count, adjusted_task_total)
    adjusted_success_delta = round(adjusted_on_success - adjusted_off_success, 2)
    adjusted_non_regression_status = "PASS" if adjusted_success_delta >= 0.0 else "FAIL"
    adjusted_success_by_library: dict[str, dict] = {}
    for library_id in sorted(set(success_by_library_off_adjusted.keys()) | set(success_by_library_on_adjusted.keys())):
        off_row = success_by_library_off_adjusted.get(library_id, {})
        on_row = success_by_library_on_adjusted.get(library_id, {})
        baseline_pct = float(off_row.get("success_at_k_pct", 0.0) or 0.0)
        retrieval_pct = float(on_row.get("success_at_k_pct", 0.0) or 0.0)
        adjusted_success_by_library[library_id] = {
            "task_count": int(on_row.get("task_count") or off_row.get("task_count") or 0),
            "baseline_off_success_at_k_pct": baseline_pct,
            "retrieval_on_success_at_k_pct": retrieval_pct,
            "delta_pp": round(retrieval_pct - baseline_pct, 2),
        }

    evidence_status = "PASS" if not missing else "FAIL"
    primary_reason = "none"
    gate_status = "PASS"
    decision = "promote"

    if missing:
        gate_status = "FAIL"
        decision = "hold"
        primary_reason = f"artifact_missing:{missing[0]}"
    elif total_tasks <= 0:
        gate_status = "FAIL"
        decision = "hold"
        primary_reason = "taskset_empty"
    elif provenance_completeness < 100.0:
        gate_status = "FAIL"
        decision = "hold"
        primary_reason = "provenance_incomplete"
    elif non_regression_status != "PASS":
        gate_status = "FAIL"
        decision = "hold"
        primary_reason = "retrieval_regression"
    elif on_success < float(args.min_retrieval_on_success_at_k_pct):
        gate_status = "NEEDS_REVIEW"
        decision = "review"
        primary_reason = "retrieval_on_success_below_threshold"
    elif retrieval_coverage < float(args.min_retrieval_coverage_pct):
        gate_status = "NEEDS_REVIEW"
        decision = "review"
        primary_reason = "retrieval_coverage_below_threshold"
    elif diagnostic_parse_coverage < float(args.min_diagnostic_parse_coverage_pct):
        gate_status = "NEEDS_REVIEW"
        decision = "review"
        primary_reason = "diagnostic_parse_coverage_below_threshold"
    elif match_signal_coverage < 50.0:
        gate_status = "NEEDS_REVIEW"
        decision = "review"
        primary_reason = "match_signal_coverage_below_threshold"

    library_summary = retrieval_summary.get("counts_by_library") if isinstance(retrieval_summary.get("counts_by_library"), dict) else {}
    transferability_by_library = {key: _decision_for_library(value) for key, value in library_summary.items()}
    knowledge_gap_candidates = [key for key, value in library_summary.items() if _decision_for_library(value) != "transferability_signal"]

    evidence_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": evidence_status,
        "taskset_coverage": {
            "total_tasks": total_tasks,
            "counts_by_library": counts_by_library,
            "provenance_completeness_pct": provenance_completeness,
        },
        "success_at_k": {
            "baseline_off_pct": off_success,
            "retrieval_on_pct": on_success,
            "delta_pp": success_delta,
        },
        "retrieval_coverage_pct": retrieval_coverage,
        "match_signal_coverage_pct": match_signal_coverage,
        "diagnostic_parse_coverage_pct": diagnostic_parse_coverage,
        "non_regression_status": non_regression_status,
        "failure_breakdown": {
            **failure_breakdown,
            "provenance_incomplete_count": provenance_incomplete_count,
        },
        "source_unstable_summary": source_unstable,
        "adjusted_excluding_source_unstable": {
            "total_tasks": adjusted_task_total,
            "success_at_k": {
                "baseline_off_pct": adjusted_off_success,
                "retrieval_on_pct": adjusted_on_success,
                "delta_pp": adjusted_success_delta,
            },
            "non_regression_status": adjusted_non_regression_status,
            "success_by_library": adjusted_success_by_library,
        },
        "success_by_library": success_by_library,
        "sources": {
            "challenge_summary": args.challenge_summary,
            "baseline_off_summary": args.baseline_off_summary,
            "baseline_off_results": args.baseline_off_results,
            "retrieval_on_summary": args.retrieval_on_summary,
            "retrieval_on_results": args.retrieval_on_results,
            "retrieval_summary": args.retrieval_summary,
        },
    }
    gate_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "decision": decision,
        "primary_reason": primary_reason,
        "counts_by_library": counts_by_library,
        "retrieval_coverage_pct": retrieval_coverage,
        "diagnostic_parse_coverage_pct": diagnostic_parse_coverage,
        "non_regression_status": non_regression_status,
        "source_unstable_model_count": int(source_unstable.get("model_count") or 0),
        "source_unstable_task_count": int(source_unstable.get("task_count") or 0),
        "adjusted_non_regression_status": adjusted_non_regression_status,
        "adjusted_success_at_k": evidence_summary.get("adjusted_excluding_source_unstable", {}).get("success_at_k"),
        "thresholds": {
            "min_retrieval_on_success_at_k_pct": float(args.min_retrieval_on_success_at_k_pct),
            "min_retrieval_coverage_pct": float(args.min_retrieval_coverage_pct),
            "min_diagnostic_parse_coverage_pct": float(args.min_diagnostic_parse_coverage_pct),
        },
        "success_by_library": success_by_library,
    }
    decision_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "decision": decision,
        "primary_reason": primary_reason,
        "counts_by_library": counts_by_library,
        "retrieval_coverage_pct": retrieval_coverage,
        "non_regression_status": non_regression_status,
        "source_unstable_summary": source_unstable,
        "adjusted_excluding_source_unstable": evidence_summary.get("adjusted_excluding_source_unstable"),
        "libraries_with_transferability_signal": [key for key, value in transferability_by_library.items() if value == "transferability_signal"],
        "libraries_with_generic_fallback": [key for key, value in transferability_by_library.items() if value != "transferability_signal"],
        "library_transferability": transferability_by_library,
        "success_by_library": success_by_library,
        "next_priority_knowledge_gap": knowledge_gap_candidates[0] if knowledge_gap_candidates else "none",
        "failure_breakdown": evidence_summary.get("failure_breakdown"),
    }

    _write_json(args.out, evidence_summary)
    _write_json(args.gate_out, gate_summary)
    _write_json(args.decision_out, decision_summary)
    exclusions_out = str(args.source_unstable_exclusions_out or "").strip()
    if not exclusions_out:
        exclusions_out = str(Path(args.decision_out).with_name("source_unstable_exclusions.json"))
    exclusions_payload = {
        "schema_version": "agent_modelica_unknown_library_source_unstable_exclusions_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "exclude_source_unstable_models_from_unknown_library_baseline",
        "qualified_model_names": source_unstable.get("qualified_model_names"),
        "model_ids": source_unstable.get("model_ids"),
        "library_ids": source_unstable.get("library_ids"),
        "task_ids": source_unstable.get("task_ids"),
        "counts_by_library": source_unstable.get("counts_by_library"),
        "models": source_unstable.get("models"),
        "sources": {
            "taskset": challenge.get("taskset_frozen_path") or "",
            "baseline_off_results": args.baseline_off_results,
            "retrieval_on_results": args.retrieval_on_results,
        },
    }
    _write_json(exclusions_out, exclusions_payload)
    _write_markdown(str(args.report_out or _default_md_path(str(args.decision_out))), decision_summary)
    print(json.dumps({"status": gate_status, "decision": decision, "primary_reason": primary_reason}))
    if gate_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
