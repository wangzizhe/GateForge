from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import canonical_error_type_v0, canonical_stage_from_failure_type_v0


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((float(num) / float(den)) * 100.0, 2)


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _expected_stage(task_map: dict[str, dict], record: dict) -> str:
    task_id = str(record.get("task_id") or "")
    from_task = str((task_map.get(task_id) or {}).get("expected_stage") or "").strip().lower()
    if from_task:
        return from_task
    return str(record.get("expected_stage") or "").strip().lower()


def _stage_hint(observed_failure_type: str, expected_stage: str) -> str:
    observed_stage = canonical_stage_from_failure_type_v0(observed_failure_type)
    if observed_stage != "none":
        return observed_stage
    expected = str(expected_stage or "").strip().lower()
    if expected in {"check", "simulate"}:
        return expected
    return "none"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Diagnostic Quality v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_attempts: `{payload.get('total_attempts')}`",
        f"- parse_coverage_pct: `{payload.get('parse_coverage_pct')}`",
        f"- canonical_type_match_rate_pct: `{payload.get('canonical_type_match_rate_pct')}`",
        f"- stage_match_rate_pct: `{payload.get('stage_match_rate_pct')}`",
        f"- low_confidence_rate_pct: `{payload.get('low_confidence_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def evaluate_diagnostic_quality_v0(
    run_results_payload: dict,
    taskset_payload: dict | None = None,
    *,
    low_confidence_threshold: float = 0.65,
) -> dict:
    records = run_results_payload.get("records") if isinstance(run_results_payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    taskset = taskset_payload if isinstance(taskset_payload, dict) else {}
    tasks = taskset.get("tasks") if isinstance(taskset.get("tasks"), list) else []
    task_map = {
        str(row.get("task_id") or ""): row
        for row in tasks
        if isinstance(row, dict) and str(row.get("task_id") or "")
    }

    total_attempts = 0
    parsed_attempts = 0
    type_comparable = 0
    type_match = 0
    stage_comparable = 0
    stage_match = 0
    by_error_type: dict[str, int] = {}
    subtype_distribution: dict[str, int] = {}
    category_distribution: dict[str, int] = {}
    observed_phase_distribution: dict[str, int] = {}
    low_confidence_count = 0
    phase_drift_count = 0

    for record in records:
        expected_stage = _expected_stage(task_map=task_map, record=record)
        task_id = str(record.get("task_id") or "")
        task_category = str((task_map.get(task_id) or {}).get("category") or "").strip().lower()
        attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
        attempts = [x for x in attempts if isinstance(x, dict)]
        for attempt in attempts:
            total_attempts += 1
            observed_failure_type = canonical_error_type_v0(str(attempt.get("observed_failure_type") or "").strip().lower())
            diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
            diag_type = canonical_error_type_v0(str(diagnostic.get("error_type") or "").strip().lower())
            diag_stage = str(diagnostic.get("stage") or "").strip().lower()
            observed_phase = str(diagnostic.get("observed_phase") or diag_stage or "").strip().lower()
            diag_subtype = str(diagnostic.get("error_subtype") or "").strip().lower()
            confidence = _to_float(diagnostic.get("confidence"), default=1.0)

            if diag_type:
                parsed_attempts += 1
                by_error_type[diag_type] = int(by_error_type.get(diag_type, 0)) + 1
                if diag_subtype and diag_subtype != "none":
                    subtype_distribution[diag_subtype] = int(subtype_distribution.get(diag_subtype, 0)) + 1
                if observed_phase in {"check", "simulate"}:
                    observed_phase_distribution[observed_phase] = int(observed_phase_distribution.get(observed_phase, 0)) + 1
                    if diag_stage in {"check", "simulate"} and observed_phase != diag_stage:
                        phase_drift_count += 1
                if task_category:
                    category_distribution[task_category] = int(category_distribution.get(task_category, 0)) + 1
                if confidence < float(low_confidence_threshold):
                    low_confidence_count += 1

            if observed_failure_type not in {"", "none"} and diag_type not in {"", "none"}:
                type_comparable += 1
                if observed_failure_type == diag_type:
                    type_match += 1

            stage_expected = _stage_hint(observed_failure_type=observed_failure_type, expected_stage=expected_stage)
            if stage_expected in {"check", "simulate"} and diag_stage in {"check", "simulate"}:
                stage_comparable += 1
                if stage_expected == diag_stage:
                    stage_match += 1

    status = "PASS"
    if total_attempts <= 0:
        status = "FAIL"
    elif parsed_attempts < total_attempts:
        status = "NEEDS_REVIEW"

    type_not_applicable = bool(total_attempts > 0 and type_comparable <= 0)
    stage_not_applicable = bool(total_attempts > 0 and stage_comparable <= 0)
    canonical_type_match_rate = 100.0 if type_not_applicable else _ratio(type_match, type_comparable)
    stage_match_rate = 100.0 if stage_not_applicable else _ratio(stage_match, stage_comparable)
    summary = {
        "schema_version": "agent_modelica_diagnostic_quality_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_attempts": total_attempts,
        "parsed_attempts": parsed_attempts,
        "parse_coverage_pct": _ratio(parsed_attempts, total_attempts),
        "canonical_type_match_rate_pct": canonical_type_match_rate,
        # Backward-compatible alias.
        "type_match_rate_pct": canonical_type_match_rate,
        "stage_match_rate_pct": stage_match_rate,
        "type_comparable_count": type_comparable,
        "stage_comparable_count": stage_comparable,
        "type_match_not_applicable": type_not_applicable,
        "stage_match_not_applicable": stage_not_applicable,
        "error_type_distribution": dict(sorted(by_error_type.items())),
        "subtype_distribution": dict(sorted(subtype_distribution.items())),
        "category_distribution": dict(sorted(category_distribution.items())),
        "observed_phase_distribution": dict(sorted(observed_phase_distribution.items())),
        "phase_drift_count": phase_drift_count,
        "phase_drift_rate_pct": _ratio(phase_drift_count, parsed_attempts),
        "low_confidence_threshold": float(low_confidence_threshold),
        "low_confidence_count": low_confidence_count,
        "low_confidence_rate_pct": _ratio(low_confidence_count, parsed_attempts),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate diagnostic parse/type/stage quality from run results")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--taskset", default="")
    parser.add_argument("--low-confidence-threshold", type=float, default=0.65)
    parser.add_argument("--out", default="artifacts/agent_modelica_diagnostic_quality_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    run_results = _load_json(args.run_results)
    taskset = _load_json(args.taskset) if str(args.taskset).strip() else {}
    summary = evaluate_diagnostic_quality_v0(
        run_results_payload=run_results,
        taskset_payload=taskset,
        low_confidence_threshold=float(args.low_confidence_threshold),
    )
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "parse_coverage_pct": summary.get("parse_coverage_pct"),
                "canonical_type_match_rate_pct": summary.get("canonical_type_match_rate_pct"),
                "stage_match_rate_pct": summary.get("stage_match_rate_pct"),
                "low_confidence_rate_pct": summary.get("low_confidence_rate_pct"),
            }
        )
    )
    if str(summary.get("status")) == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
