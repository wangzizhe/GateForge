from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import canonical_error_type_v0, canonical_stage_from_failure_type_v0


SCHEMA_VERSION = "agent_modelica_realism_summary_v1"


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((float(num) / float(den)) * 100.0, 2)


def _expected_canonical_type(failure_type: str) -> str:
    ftype = str(failure_type or "").strip().lower()
    if ftype in {"underconstrained_system", "connector_mismatch"}:
        return "model_check_error"
    if ftype == "initialization_infeasible":
        return "simulate_error"
    return canonical_error_type_v0(ftype)


def _expected_stage(task: dict) -> str:
    stage = str(task.get("expected_stage") or "").strip().lower()
    if stage:
        return stage
    return canonical_stage_from_failure_type_v0(_expected_canonical_type(str(task.get("failure_type") or "")))


def _expected_subtypes(failure_type: str) -> set[str]:
    ftype = str(failure_type or "").strip().lower()
    if ftype == "connector_mismatch":
        return {"connector_mismatch"}
    if ftype == "initialization_infeasible":
        return {"init_failure"}
    return set()


def _is_benign_missing_initialization_manifestation(
    *,
    declared_failure_type: str,
    record_passed: bool,
    final_failure_type: str,
    final_subtype: str,
) -> bool:
    return (
        str(declared_failure_type or "").strip().lower() == "initialization_infeasible"
        and bool(record_passed)
        and str(final_failure_type or "").strip().lower() in {"", "none"}
        and str(final_subtype or "").strip().lower() in {"", "none"}
    )


def _first_attempt(record: dict) -> dict:
    attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
    attempts = [x for x in attempts if isinstance(x, dict)]
    if not attempts:
        return {}
    return attempts[0]


def _last_attempt(record: dict) -> dict:
    attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
    attempts = [x for x in attempts if isinstance(x, dict)]
    if not attempts:
        return {}
    return attempts[-1]


def _attempt_observation(attempt: dict) -> tuple[str, str, str]:
    diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
    observed_failure_type = canonical_error_type_v0(
        str(attempt.get("observed_failure_type") or diagnostic.get("error_type") or "").strip().lower()
    )
    observed_subtype = str(diagnostic.get("error_subtype") or "none").strip().lower() or "none"
    observed_stage = str(diagnostic.get("stage") or "").strip().lower()
    if not observed_stage:
        observed_stage = canonical_stage_from_failure_type_v0(observed_failure_type)
    return observed_failure_type or "none", observed_stage or "none", observed_subtype


def _attempt_observed_phase(attempt: dict) -> str:
    diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
    observed_phase = str(diagnostic.get("observed_phase") or "").strip().lower()
    return observed_phase or "none"


def _has_failure_signal(observed_failure_type: str, observed_stage: str, observed_subtype: str) -> bool:
    return (
        str(observed_failure_type or "").strip().lower() not in {"", "none"}
        or str(observed_stage or "").strip().lower() in {"check", "simulate"}
        or str(observed_subtype or "").strip().lower() not in {"", "none"}
    )


def _manifestation_attempt(record: dict) -> dict:
    declared_failure_type = str(record.get("failure_type") or "").strip().lower()
    expected_canonical = _expected_canonical_type(declared_failure_type)
    expected_stage = canonical_stage_from_failure_type_v0(expected_canonical)
    expected_subtypes = _expected_subtypes(declared_failure_type)
    candidates = _flatten_attempt_candidates(record)
    signaled: list[tuple[dict, str, str, str]] = []
    for attempt in candidates:
        observed_failure_type, observed_stage, observed_subtype = _attempt_observation(attempt)
        if _has_failure_signal(observed_failure_type, observed_stage, observed_subtype):
            signaled.append((attempt, observed_failure_type, observed_stage, observed_subtype))
    if not signaled:
        return {}

    def _score(row: tuple[dict, str, str, str]) -> tuple[int, int, int, int]:
        _, observed_failure_type, observed_stage, observed_subtype = row
        subtype_match = 1 if (not expected_subtypes or observed_subtype in expected_subtypes) else 0
        stage_match = 1 if observed_stage == expected_stage else 0
        canonical_match = 1 if observed_failure_type == expected_canonical else 0
        non_wrapper = 0 if observed_failure_type in {"executor_runtime_error", "executor_invocation_error"} else 1
        return (canonical_match, stage_match, subtype_match, non_wrapper)

    ranked = max(enumerate(signaled), key=lambda item: (_score(item[1]), -item[0]))
    return ranked[1][0]
    return {}


def _parse_json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if not raw:
        return {}
    candidates = [raw]
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        snippet = raw[start : end + 1]
        if snippet != raw:
            candidates.append(snippet)
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _nested_attempts_from_attempt(attempt: dict) -> list[dict]:
    nested = attempt.get("attempts") if isinstance(attempt.get("attempts"), list) else []
    nested = [x for x in nested if isinstance(x, dict)]
    if nested:
        return nested
    payload = _parse_json_object(str(attempt.get("executor_stdout_tail") or ""))
    nested = payload.get("attempts") if isinstance(payload.get("attempts"), list) else []
    return [x for x in nested if isinstance(x, dict)]


def _flatten_attempt_candidates(record: dict) -> list[dict]:
    attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
    attempts = [x for x in attempts if isinstance(x, dict)]
    flattened: list[dict] = []
    for attempt in attempts:
        nested = _nested_attempts_from_attempt(attempt)
        if nested:
            flattened.extend(nested)
        flattened.append(attempt)
    return flattened


def _inc(counter: dict[str, int], key: str) -> None:
    counter[key] = int(counter.get(key, 0)) + 1


def _sorted_counter(counter: dict[str, int]) -> dict[str, int]:
    return {str(k): int(counter[k]) for k in sorted(counter.keys())}


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mismatch = payload.get("mismatch_summary") if isinstance(payload.get("mismatch_summary"), dict) else {}
    manifestation = payload.get("failure_manifestation_view") if isinstance(payload.get("failure_manifestation_view"), dict) else {}
    outcome = payload.get("final_outcome_view") if isinstance(payload.get("final_outcome_view"), dict) else {}
    lines = [
        "# Agent Modelica Realism Summary v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- recommendation: `{payload.get('recommendation')}`",
        f"- taxonomy_view_mode: `{payload.get('taxonomy_view_mode')}`",
        f"- manifestation_status: `{manifestation.get('status')}`",
        f"- outcome_status: `{outcome.get('status')}`",
        f"- pack_id: `{payload.get('pack_id')}`",
        f"- pack_version: `{payload.get('pack_version')}`",
        f"- pack_track: `{payload.get('pack_track')}`",
        f"- acceptance_scope: `{payload.get('acceptance_scope')}`",
        f"- acceptance_mode: `{payload.get('acceptance_mode')}`",
        f"- l5_gate_result: `{payload.get('l5_gate_result')}`",
        f"- l5_success_at_k_pct: `{payload.get('l5_success_at_k_pct')}`",
        f"- connector_subtype_match_rate_pct: `{mismatch.get('connector_subtype_match_rate_pct')}`",
        f"- initialization_simulate_stage_rate_pct: `{mismatch.get('initialization_simulate_stage_rate_pct')}`",
        f"- initialization_truncated_by_check_count: `{mismatch.get('initialization_truncated_by_check_count')}`",
        f"- missing_failure_signal_count: `{mismatch.get('missing_failure_signal_count')}`",
        f"- phase_drift_count: `{mismatch.get('phase_drift_count')}`",
        "",
        "## Counts",
        "",
        f"- challenge_counts_by_failure_type: `{payload.get('challenge_counts_by_failure_type')}`",
        f"- challenge_counts_by_category: `{payload.get('challenge_counts_by_category')}`",
        f"- l3_category_distribution: `{payload.get('l3_category_distribution')}`",
        f"- l3_task_category_distribution: `{payload.get('l3_task_category_distribution')}`",
        f"- l5_category_breakdown_on: `{payload.get('l5_category_breakdown_on')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _blocked_summary(
    *,
    evidence_summary: dict,
    challenge_summary: dict,
    challenge_manifest: dict,
    taskset_payload: dict,
    reasons: list[str],
) -> dict:
    tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    declared_counts_by_failure: dict[str, int] = {}
    declared_counts_by_category: dict[str, int] = {}
    for task in tasks:
        _inc(declared_counts_by_failure, str(task.get("failure_type") or "").strip().lower())
        _inc(declared_counts_by_category, str(task.get("category") or "").strip().lower())

    challenge_counts_by_failure_type = challenge_summary.get("counts_by_failure_type") if isinstance(challenge_summary.get("counts_by_failure_type"), dict) else {}
    challenge_counts_by_category = challenge_summary.get("counts_by_category") if isinstance(challenge_summary.get("counts_by_category"), dict) else {}
    baseline_provenance = challenge_manifest.get("baseline_provenance") if isinstance(challenge_manifest.get("baseline_provenance"), dict) else {}

    by_failure_type = {
        failure_type: {
            "task_count": int(count),
            "l3_record_count": 0,
            "manifestation_record_count": 0,
            "canonical_match_rate_pct": 0.0,
            "stage_match_rate_pct": 0.0,
            "subtype_match_rate_pct": 0.0,
            "no_failure_signal_count": 0,
            "resolved_task_count": 0,
            "resolved_after_aligned_manifestation_count": 0,
            "resolved_without_failure_signal_count": 0,
            "observed_failure_type_distribution": {},
            "observed_subtype_distribution": {},
            "observed_phase_distribution": {},
            "phase_drift_count": 0,
            "final_observed_failure_type_distribution": {},
            "final_observed_subtype_distribution": {},
            "mismatch_reasons": {},
            "l5_success_count_on": 0,
        }
        for failure_type, count in sorted(declared_counts_by_failure.items())
    }
    category_alignment = {
        category: {
            "expected_task_count": int(count),
            "l3_task_category_count": 0,
            "l3_attempt_category_count": 0,
            "l5_record_count_on": 0,
            "counts_match": False,
        }
        for category, count in sorted(declared_counts_by_category.items())
    }
    mismatch_summary = {
        "canonical_type_mismatch_count": 0,
        "stage_mismatch_count": 0,
        "subtype_mismatch_count": 0,
        "missing_failure_signal_count": 0,
        "phase_drift_count": 0,
        "initialization_truncated_by_check_count": 0,
        "connector_subtype_match_rate_pct": 100.0,
        "initialization_simulate_stage_rate_pct": 100.0,
        "category_record_gap_count": len(category_alignment),
        "missing_failure_type_records": sorted(by_failure_type.keys()),
        "missing_categories": [],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "recommendation": "blocked_missing_realism_inputs",
        "reasons": sorted(set([str(x) for x in reasons if str(x)])),
        "taxonomy_view_mode": "dual_view",
        "pack_id": str(evidence_summary.get("pack_id") or challenge_summary.get("pack_id") or ""),
        "pack_version": str(evidence_summary.get("pack_version") or challenge_summary.get("pack_version") or ""),
        "pack_track": str(evidence_summary.get("pack_track") or challenge_summary.get("pack_track") or ""),
        "acceptance_scope": str(evidence_summary.get("acceptance_scope") or challenge_summary.get("acceptance_scope") or ""),
        "acceptance_mode": str(evidence_summary.get("acceptance_mode") or ""),
        "l5_gate_result": "",
        "l5_success_at_k_pct": None,
        "challenge_counts_by_failure_type": challenge_counts_by_failure_type,
        "challenge_counts_by_category": challenge_counts_by_category,
        "l3_category_distribution": {},
        "l3_task_category_distribution": {},
        "l3_subtype_distribution": {},
        "l5_category_breakdown_on": {},
        "l5_failure_type_breakdown_on": {},
        "by_failure_type": by_failure_type,
        "category_alignment": category_alignment,
        "mismatch_summary": mismatch_summary,
        "failure_manifestation_view": {
            "status": "BLOCKED",
            "by_failure_type": by_failure_type,
            "mismatch_summary": mismatch_summary,
        },
        "final_outcome_view": {
            "status": "BLOCKED",
            "resolved_task_count": 0,
            "unresolved_task_count": len(tasks),
            "resolved_after_aligned_manifestation_count": 0,
            "resolved_without_failure_signal_count": 0,
        },
        "environment": {
            "planner_backend": str(baseline_provenance.get("planner_backend") or ""),
            "llm_model": baseline_provenance.get("llm_model"),
            "backend": str(baseline_provenance.get("backend") or ""),
            "docker_image": str(baseline_provenance.get("docker_image") or ""),
            "max_rounds": baseline_provenance.get("max_rounds"),
            "max_time_sec": baseline_provenance.get("max_time_sec"),
        },
    }


def build_realism_summary_v1(
    *,
    evidence_summary: dict,
    challenge_summary: dict,
    challenge_manifest: dict,
    taskset_payload: dict,
    l3_run_results: dict,
    l3_quality_summary: dict,
    l4_ab_compare_summary: dict,
    l5_summary: dict,
) -> dict:
    missing_inputs: list[str] = []
    l3_records_probe = l3_run_results.get("records") if isinstance(l3_run_results.get("records"), list) else []
    if not isinstance(l3_run_results, dict) or not l3_records_probe:
        missing_inputs.append("l3_run_results_missing")
    if not isinstance(l3_quality_summary, dict) or not l3_quality_summary:
        missing_inputs.append("l3_quality_summary_missing")
    if not isinstance(l5_summary, dict) or not l5_summary:
        missing_inputs.append("l5_summary_missing")
    if missing_inputs:
        return _blocked_summary(
            evidence_summary=evidence_summary,
            challenge_summary=challenge_summary,
            challenge_manifest=challenge_manifest,
            taskset_payload=taskset_payload,
            reasons=missing_inputs,
        )

    l5_primary_reason = str(l5_summary.get("primary_reason") or "").strip()
    l5_reasons = [str(x).strip() for x in (l5_summary.get("reasons") or []) if str(x).strip()]
    for key in ("live_request_budget_exceeded", "rate_limited"):
        if l5_primary_reason == key or key in l5_reasons:
            return _blocked_summary(
                evidence_summary=evidence_summary,
                challenge_summary=challenge_summary,
                challenge_manifest=challenge_manifest,
                taskset_payload=taskset_payload,
                reasons=[key],
            )

    tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    task_map = {
        str(row.get("task_id") or ""): row
        for row in tasks
        if str(row.get("task_id") or "").strip()
    }
    declared_counts_by_failure: dict[str, int] = {}
    declared_counts_by_category: dict[str, int] = {}
    for task in tasks:
        _inc(declared_counts_by_failure, str(task.get("failure_type") or "").strip().lower())
        _inc(declared_counts_by_category, str(task.get("category") or "").strip().lower())

    l3_records = l3_run_results.get("records") if isinstance(l3_run_results.get("records"), list) else []
    l3_records = [x for x in l3_records if isinstance(x, dict)]
    l3_task_category_distribution: dict[str, int] = {}

    by_failure_type: dict[str, dict] = {}
    initialization_truncated_by_check_count = 0
    connector_subtype_match_count = 0
    connector_record_count = 0
    initialization_simulate_stage_count = 0
    initialization_record_count = 0
    total_canonical_mismatch = 0
    total_stage_mismatch = 0
    total_subtype_mismatch = 0
    total_missing_failure_signal = 0
    total_phase_drift = 0
    resolved_task_count = 0
    resolved_after_aligned_manifestation_count = 0
    resolved_without_failure_signal_count = 0

    for failure_type in sorted(declared_counts_by_failure.keys()):
        by_failure_type[failure_type] = {
            "task_count": int(declared_counts_by_failure.get(failure_type, 0)),
            "l3_record_count": 0,
            "manifestation_record_count": 0,
            "canonical_match_count": 0,
            "stage_match_count": 0,
            "subtype_match_count": 0,
            "no_failure_signal_count": 0,
            "resolved_task_count": 0,
            "resolved_after_aligned_manifestation_count": 0,
            "resolved_without_failure_signal_count": 0,
            "manifestation_failure_type_distribution": {},
            "manifestation_subtype_distribution": {},
            "manifestation_phase_distribution": {},
            "phase_drift_count": 0,
            "final_failure_type_distribution": {},
            "final_subtype_distribution": {},
            "mismatch_reasons": {},
        }

    for record in l3_records:
        task_id = str(record.get("task_id") or "")
        task = task_map.get(task_id) if isinstance(task_map.get(task_id), dict) else {}
        task_category = str(task.get("category") or "").strip().lower()
        if task_category:
            _inc(l3_task_category_distribution, task_category)
        declared_failure_type = str(task.get("failure_type") or record.get("failure_type") or "").strip().lower()
        if not declared_failure_type:
            continue
        row = by_failure_type.setdefault(
            declared_failure_type,
            {
                "task_count": int(declared_counts_by_failure.get(declared_failure_type, 0)),
                "l3_record_count": 0,
                "manifestation_record_count": 0,
                "canonical_match_count": 0,
                "stage_match_count": 0,
                "subtype_match_count": 0,
                "no_failure_signal_count": 0,
                "resolved_task_count": 0,
                "resolved_after_aligned_manifestation_count": 0,
                "resolved_without_failure_signal_count": 0,
                "manifestation_failure_type_distribution": {},
                "manifestation_subtype_distribution": {},
                "manifestation_phase_distribution": {},
                "phase_drift_count": 0,
                "final_failure_type_distribution": {},
                "final_subtype_distribution": {},
                "mismatch_reasons": {},
            },
        )
        row["l3_record_count"] = int(row.get("l3_record_count", 0)) + 1

        manifestation_attempt = _manifestation_attempt(record)
        final_attempt = _last_attempt(record)
        manifestation_failure_type, manifestation_stage, manifestation_subtype = _attempt_observation(manifestation_attempt or {})
        manifestation_phase = _attempt_observed_phase(manifestation_attempt or {})
        final_failure_type, final_stage, final_subtype = _attempt_observation(final_attempt or {})
        record_passed = bool(record.get("passed"))
        expected_canonical = _expected_canonical_type(declared_failure_type)
        expected_stage = _expected_stage(task)
        expected_subtypes = _expected_subtypes(declared_failure_type)

        _inc(row["final_failure_type_distribution"], final_failure_type or "none")
        _inc(row["final_subtype_distribution"], final_subtype or "none")

        if record_passed:
            resolved_task_count += 1
            row["resolved_task_count"] = int(row.get("resolved_task_count", 0)) + 1

        if _has_failure_signal(manifestation_failure_type, manifestation_stage, manifestation_subtype):
            row["manifestation_record_count"] = int(row.get("manifestation_record_count", 0)) + 1
            _inc(row["manifestation_failure_type_distribution"], manifestation_failure_type or "none")
            _inc(row["manifestation_subtype_distribution"], manifestation_subtype or "none")
            _inc(row["manifestation_phase_distribution"], manifestation_phase or "none")

            canonical_match = manifestation_failure_type == expected_canonical
            stage_match = manifestation_stage == expected_stage
            subtype_match = True if not expected_subtypes else manifestation_subtype in expected_subtypes
            phase_drift = manifestation_phase in {"check", "simulate"} and manifestation_phase != manifestation_stage

            if canonical_match:
                row["canonical_match_count"] = int(row.get("canonical_match_count", 0)) + 1
            else:
                _inc(row["mismatch_reasons"], "canonical_type_mismatch")
                total_canonical_mismatch += 1
            if stage_match:
                row["stage_match_count"] = int(row.get("stage_match_count", 0)) + 1
            else:
                _inc(row["mismatch_reasons"], "stage_mismatch")
                total_stage_mismatch += 1
            if subtype_match:
                row["subtype_match_count"] = int(row.get("subtype_match_count", 0)) + 1
            else:
                _inc(row["mismatch_reasons"], "subtype_mismatch")
                total_subtype_mismatch += 1
            if phase_drift:
                row["phase_drift_count"] = int(row.get("phase_drift_count", 0)) + 1
                _inc(row["mismatch_reasons"], "phase_drift")
                total_phase_drift += 1

            if record_passed and canonical_match and stage_match and subtype_match:
                resolved_after_aligned_manifestation_count += 1
                row["resolved_after_aligned_manifestation_count"] = int(row.get("resolved_after_aligned_manifestation_count", 0)) + 1

            if declared_failure_type == "connector_mismatch":
                connector_record_count += 1
                if subtype_match:
                    connector_subtype_match_count += 1
            if declared_failure_type == "initialization_infeasible":
                initialization_record_count += 1
                if manifestation_stage == "simulate":
                    initialization_simulate_stage_count += 1
                if manifestation_stage == "check" or manifestation_failure_type == "model_check_error":
                    initialization_truncated_by_check_count += 1
                    _inc(row["mismatch_reasons"], "truncated_by_check")
        else:
            row["no_failure_signal_count"] = int(row.get("no_failure_signal_count", 0)) + 1
            if record_passed:
                resolved_without_failure_signal_count += 1
                row["resolved_without_failure_signal_count"] = int(row.get("resolved_without_failure_signal_count", 0)) + 1
            benign_missing_initialization_manifestation = _is_benign_missing_initialization_manifestation(
                declared_failure_type=declared_failure_type,
                record_passed=record_passed,
                final_failure_type=final_failure_type,
                final_subtype=final_subtype,
            )
            if benign_missing_initialization_manifestation:
                _inc(row["mismatch_reasons"], "resolved_without_failure_signal")
            else:
                _inc(row["mismatch_reasons"], "missing_failure_signal")
                total_missing_failure_signal += 1

    failure_type_breakdown_on = l5_summary.get("failure_type_breakdown_on") if isinstance(l5_summary.get("failure_type_breakdown_on"), dict) else {}
    category_breakdown_on = l5_summary.get("category_breakdown_on") if isinstance(l5_summary.get("category_breakdown_on"), dict) else {}
    l3_category_distribution = l3_quality_summary.get("category_distribution") if isinstance(l3_quality_summary.get("category_distribution"), dict) else {}
    l3_subtype_distribution = l3_quality_summary.get("subtype_distribution") if isinstance(l3_quality_summary.get("subtype_distribution"), dict) else {}

    category_alignment: dict[str, dict] = {}
    category_record_gap_count = 0
    for category in sorted(declared_counts_by_category.keys()):
        expected_count = int(declared_counts_by_category.get(category, 0))
        l3_count = int(l3_task_category_distribution.get(category, 0))
        l5_row = category_breakdown_on.get(category) if isinstance(category_breakdown_on.get(category), dict) else {}
        l5_record_count = _to_int(l5_row.get("record_count"), 0)
        counts_match = expected_count == l5_record_count and expected_count == l3_count
        if not counts_match:
            category_record_gap_count += 1
        category_alignment[category] = {
            "expected_task_count": expected_count,
            "l3_task_category_count": l3_count,
            "l3_attempt_category_count": int(l3_category_distribution.get(category, 0)),
            "l5_record_count_on": l5_record_count,
            "counts_match": counts_match,
        }

    by_failure_type_summary: dict[str, dict] = {}
    missing_failure_type_records: list[str] = []
    for failure_type, row in by_failure_type.items():
        l3_record_count = int(row.get("l3_record_count", 0))
        manifestation_record_count = int(row.get("manifestation_record_count", 0))
        if l3_record_count <= 0:
            missing_failure_type_records.append(failure_type)
        summary = {
            "task_count": int(row.get("task_count", 0)),
            "l3_record_count": l3_record_count,
            "manifestation_record_count": manifestation_record_count,
            "canonical_match_rate_pct": _ratio(int(row.get("canonical_match_count", 0)), manifestation_record_count),
            "stage_match_rate_pct": _ratio(int(row.get("stage_match_count", 0)), manifestation_record_count),
            "subtype_match_rate_pct": _ratio(int(row.get("subtype_match_count", 0)), manifestation_record_count),
            "no_failure_signal_count": int(row.get("no_failure_signal_count", 0)),
            "phase_drift_count": int(row.get("phase_drift_count", 0)),
            "resolved_task_count": int(row.get("resolved_task_count", 0)),
            "resolved_after_aligned_manifestation_count": int(row.get("resolved_after_aligned_manifestation_count", 0)),
            "resolved_without_failure_signal_count": int(row.get("resolved_without_failure_signal_count", 0)),
            "observed_failure_type_distribution": _sorted_counter(
                row.get("manifestation_failure_type_distribution") if isinstance(row.get("manifestation_failure_type_distribution"), dict) else {}
            ),
            "observed_subtype_distribution": _sorted_counter(
                row.get("manifestation_subtype_distribution") if isinstance(row.get("manifestation_subtype_distribution"), dict) else {}
            ),
            "observed_phase_distribution": _sorted_counter(
                row.get("manifestation_phase_distribution") if isinstance(row.get("manifestation_phase_distribution"), dict) else {}
            ),
            "final_observed_failure_type_distribution": _sorted_counter(
                row.get("final_failure_type_distribution") if isinstance(row.get("final_failure_type_distribution"), dict) else {}
            ),
            "final_observed_subtype_distribution": _sorted_counter(
                row.get("final_subtype_distribution") if isinstance(row.get("final_subtype_distribution"), dict) else {}
            ),
            "mismatch_reasons": _sorted_counter(row.get("mismatch_reasons") if isinstance(row.get("mismatch_reasons"), dict) else {}),
            "l5_success_count_on": _to_int(
                (
                    failure_type_breakdown_on.get(failure_type)
                    if isinstance(failure_type_breakdown_on.get(failure_type), dict)
                    else {}
                ).get("success_count"),
                0,
            ),
        }
        by_failure_type_summary[failure_type] = summary

    challenge_counts_by_failure_type = challenge_summary.get("counts_by_failure_type") if isinstance(challenge_summary.get("counts_by_failure_type"), dict) else {}
    challenge_counts_by_category = challenge_summary.get("counts_by_category") if isinstance(challenge_summary.get("counts_by_category"), dict) else {}
    missing_categories = [x for x, count in declared_counts_by_category.items() if int(count or 0) <= 0]
    connector_subtype_match_rate_pct = 100.0 if connector_record_count <= 0 else _ratio(connector_subtype_match_count, connector_record_count)
    initialization_simulate_stage_rate_pct = 100.0 if initialization_record_count <= 0 else _ratio(initialization_simulate_stage_count, initialization_record_count)
    l5_success_total = sum(
        _to_int(
            (
                failure_type_breakdown_on.get(failure_type)
                if isinstance(failure_type_breakdown_on.get(failure_type), dict)
                else {}
            ).get("success_count"),
            0,
        )
        for failure_type in declared_counts_by_failure.keys()
    )
    outcome_resolved_task_count = max(resolved_task_count, l5_success_total)

    mismatch_summary = {
        "canonical_type_mismatch_count": total_canonical_mismatch,
        "stage_mismatch_count": total_stage_mismatch,
        "subtype_mismatch_count": total_subtype_mismatch,
        "missing_failure_signal_count": total_missing_failure_signal,
        "phase_drift_count": total_phase_drift,
        "initialization_truncated_by_check_count": initialization_truncated_by_check_count,
        "connector_subtype_match_rate_pct": connector_subtype_match_rate_pct,
        "initialization_simulate_stage_rate_pct": initialization_simulate_stage_rate_pct,
        "category_record_gap_count": category_record_gap_count,
        "missing_failure_type_records": missing_failure_type_records,
        "missing_categories": missing_categories,
    }

    manifestation_status = "PASS"
    if missing_failure_type_records or missing_categories:
        manifestation_status = "FAIL"
    elif (
        initialization_truncated_by_check_count > 0
        or connector_subtype_match_rate_pct < 50.0
        or category_record_gap_count > 0
        or total_canonical_mismatch > 0
        or total_stage_mismatch > 0
        or total_subtype_mismatch > 0
        or total_missing_failure_signal > 0
    ):
        manifestation_status = "NEEDS_REVIEW"

    outcome_status = "PASS" if outcome_resolved_task_count >= len(tasks) and tasks else "NEEDS_REVIEW"
    status = manifestation_status

    recommendation = "ready_for_next_realism_iteration"
    if status == "FAIL" or initialization_truncated_by_check_count > 0:
        recommendation = "repair_wave1_mutations"
    elif status == "NEEDS_REVIEW":
        recommendation = "repair_wave1_taxonomy_alignment"

    baseline_provenance = challenge_manifest.get("baseline_provenance") if isinstance(challenge_manifest.get("baseline_provenance"), dict) else {}
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "recommendation": recommendation,
        "taxonomy_view_mode": "dual_view",
        "pack_id": str(evidence_summary.get("pack_id") or challenge_summary.get("pack_id") or ""),
        "pack_version": str(evidence_summary.get("pack_version") or challenge_summary.get("pack_version") or ""),
        "pack_track": str(evidence_summary.get("pack_track") or challenge_summary.get("pack_track") or ""),
        "acceptance_scope": str(evidence_summary.get("acceptance_scope") or challenge_summary.get("acceptance_scope") or ""),
        "acceptance_mode": str(evidence_summary.get("acceptance_mode") or l5_summary.get("acceptance_mode") or ""),
        "l5_gate_result": str(l5_summary.get("gate_result") or l5_summary.get("status") or ""),
        "l5_success_at_k_pct": l5_summary.get("success_at_k_pct"),
        "challenge_counts_by_failure_type": challenge_counts_by_failure_type,
        "challenge_counts_by_category": challenge_counts_by_category,
        "l3_category_distribution": l3_category_distribution,
        "l3_task_category_distribution": _sorted_counter(l3_task_category_distribution),
        "l3_subtype_distribution": l3_subtype_distribution,
        "l5_category_breakdown_on": category_breakdown_on,
        "l5_failure_type_breakdown_on": failure_type_breakdown_on,
        "by_failure_type": by_failure_type_summary,
        "category_alignment": category_alignment,
        "mismatch_summary": mismatch_summary,
        "failure_manifestation_view": {
            "status": manifestation_status,
            "by_failure_type": by_failure_type_summary,
            "mismatch_summary": mismatch_summary,
        },
        "final_outcome_view": {
            "status": outcome_status,
            "resolved_task_count": outcome_resolved_task_count,
            "unresolved_task_count": max(0, len(tasks) - outcome_resolved_task_count),
            "resolved_after_aligned_manifestation_count": resolved_after_aligned_manifestation_count,
            "resolved_without_failure_signal_count": resolved_without_failure_signal_count,
        },
        "environment": {
            "planner_backend": str(baseline_provenance.get("planner_backend") or ""),
            "llm_model": baseline_provenance.get("llm_model"),
            "backend": str(baseline_provenance.get("backend") or ""),
            "docker_image": str(baseline_provenance.get("docker_image") or ""),
            "max_rounds": baseline_provenance.get("max_rounds"),
            "max_time_sec": baseline_provenance.get("max_time_sec"),
        },
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build realism v1 mismatch-focused summary from challenge/L3/L4/L5 artifacts")
    parser.add_argument("--evidence-summary", required=True)
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--challenge-manifest", required=True)
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--l3-run-results", required=True)
    parser.add_argument("--l3-quality-summary", required=True)
    parser.add_argument("--l4-ab-compare-summary", required=True)
    parser.add_argument("--l5-summary", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_realism_summary_v1/summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    summary = build_realism_summary_v1(
        evidence_summary=_load_json(args.evidence_summary),
        challenge_summary=_load_json(args.challenge_summary),
        challenge_manifest=_load_json(args.challenge_manifest),
        taskset_payload=_load_json(args.taskset),
        l3_run_results=_load_json(args.l3_run_results),
        l3_quality_summary=_load_json(args.l3_quality_summary),
        l4_ab_compare_summary=_load_json(args.l4_ab_compare_summary),
        l5_summary=_load_json(args.l5_summary),
    )
    summary["inputs"] = {
        "evidence_summary": str(args.evidence_summary),
        "challenge_summary": str(args.challenge_summary),
        "challenge_manifest": str(args.challenge_manifest),
        "taskset": str(args.taskset),
        "l3_run_results": str(args.l3_run_results),
        "l3_quality_summary": str(args.l3_quality_summary),
        "l4_ab_compare_summary": str(args.l4_ab_compare_summary),
        "l5_summary": str(args.l5_summary),
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "recommendation": summary.get("recommendation"),
                "connector_subtype_match_rate_pct": (summary.get("mismatch_summary") or {}).get("connector_subtype_match_rate_pct"),
                "initialization_truncated_by_check_count": (summary.get("mismatch_summary") or {}).get("initialization_truncated_by_check_count"),
            }
        )
    )


if __name__ == "__main__":
    main()
