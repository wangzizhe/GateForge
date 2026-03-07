from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((float(num) / float(den)) * 100.0, 2)


def evaluate_diagnostic_quality_v0(run_results_payload: dict, taskset_payload: dict | None = None) -> dict:
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

    for record in records:
        task_id = str(record.get("task_id") or "")
        expected_stage = str((task_map.get(task_id) or {}).get("expected_stage") or record.get("expected_stage") or "").strip().lower()
        attempts = record.get("attempts") if isinstance(record.get("attempts"), list) else []
        attempts = [x for x in attempts if isinstance(x, dict)]
        for attempt in attempts:
            total_attempts += 1
            observed_failure_type = str(attempt.get("observed_failure_type") or "").strip().lower()
            diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
            diag_type = str(diagnostic.get("error_type") or "").strip().lower()
            diag_stage = str(diagnostic.get("stage") or "").strip().lower()
            if diag_type:
                parsed_attempts += 1
                by_error_type[diag_type] = int(by_error_type.get(diag_type, 0)) + 1
            if observed_failure_type and diag_type:
                type_comparable += 1
                if observed_failure_type == diag_type:
                    type_match += 1
            if expected_stage and diag_stage and diag_stage != "none":
                stage_comparable += 1
                if expected_stage == diag_stage:
                    stage_match += 1

    status = "PASS"
    if total_attempts <= 0:
        status = "FAIL"
    elif parsed_attempts < total_attempts:
        status = "NEEDS_REVIEW"

    return {
        "schema_version": "agent_modelica_diagnostic_quality_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_attempts": total_attempts,
        "parsed_attempts": parsed_attempts,
        "parse_coverage_pct": _ratio(parsed_attempts, total_attempts),
        "type_match_rate_pct": _ratio(type_match, type_comparable),
        "stage_match_rate_pct": _ratio(stage_match, stage_comparable),
        "type_comparable_count": type_comparable,
        "stage_comparable_count": stage_comparable,
        "error_type_distribution": dict(sorted(by_error_type.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate diagnostic parse/type/stage quality from run results")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--taskset", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_diagnostic_quality_v0/summary.json")
    args = parser.parse_args()

    run_results = _load_json(args.run_results)
    taskset = _load_json(args.taskset) if str(args.taskset).strip() else {}
    summary = evaluate_diagnostic_quality_v0(run_results_payload=run_results, taskset_payload=taskset)
    _write_json(args.out, summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "parse_coverage_pct": summary.get("parse_coverage_pct"),
                "type_match_rate_pct": summary.get("type_match_rate_pct"),
                "stage_match_rate_pct": summary.get("stage_match_rate_pct"),
            }
        )
    )
    if str(summary.get("status")) == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
