from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_unknown_library_retrieval_summary_v1"


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
        "# GateForge Agent Modelica Unknown Library Retrieval Summary v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- retrieval_coverage_pct: `{payload.get('retrieval_coverage_pct')}`",
        f"- match_signal_coverage_pct: `{payload.get('match_signal_coverage_pct')}`",
        f"- fallback_ratio_pct: `{payload.get('fallback_ratio_pct')}`",
        f"- diagnostic_parse_coverage_pct: `{payload.get('diagnostic_parse_coverage_pct')}`",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _mean(total: int | float, count: int) -> float:
    if count <= 0:
        return 0.0
    return round(float(total) / float(count), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize unknown-library retrieval coverage from run-contract outputs")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_unknown_library_retrieval_summary_v1/summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    taskset = _load_json(args.taskset)
    results = _load_json(args.results)
    tasks = [row for row in (taskset.get("tasks") or []) if isinstance(row, dict)]
    records = [row for row in (results.get("records") or []) if isinstance(row, dict)]
    task_index = {str(row.get("task_id") or ""): row for row in tasks if str(row.get("task_id") or "").strip()}

    retrieval_task_count = 0
    match_signal_task_count = 0
    fallback_count = 0
    diagnostic_parse_count = 0
    library_match_total = 0
    component_match_total = 0
    connector_match_total = 0
    counts_by_library: dict[str, dict] = {}

    for record in records:
        task_id = str(record.get("task_id") or "")
        task = task_index.get(task_id, {})
        library_id = str(((task.get("source_meta") or {}) if isinstance(task.get("source_meta"), dict) else {}).get("library_id") or task.get("source_library") or "unknown").lower()
        per_library = counts_by_library.setdefault(
            library_id,
            {
                "task_count": 0,
                "retrieved_task_count": 0,
                "match_signal_task_count": 0,
                "fallback_count": 0,
            },
        )
        per_library["task_count"] += 1

        audit = record.get("repair_audit") if isinstance(record.get("repair_audit"), dict) else {}
        retrieved_examples = int(audit.get("retrieved_example_count", 0) or 0)
        library_match_count = int(audit.get("library_match_count", 0) or 0)
        component_match_count = int(audit.get("component_match_count", 0) or 0)
        connector_match_count = int(audit.get("connector_match_count", 0) or 0)
        fallback_used = bool(audit.get("retrieval_fallback_used", False))
        diagnostic_error_type = str(audit.get("diagnostic_error_type") or "").strip().lower()

        if retrieved_examples > 0:
            retrieval_task_count += 1
            per_library["retrieved_task_count"] += 1
        if any(value > 0 for value in (library_match_count, component_match_count, connector_match_count)):
            match_signal_task_count += 1
            per_library["match_signal_task_count"] += 1
        if fallback_used:
            fallback_count += 1
            per_library["fallback_count"] += 1
        if diagnostic_error_type:
            diagnostic_parse_count += 1

        library_match_total += library_match_count
        component_match_total += component_match_count
        connector_match_total += connector_match_count

    for value in counts_by_library.values():
        task_count = int(value.get("task_count") or 0)
        value["retrieval_coverage_pct"] = _ratio(int(value.get("retrieved_task_count") or 0), task_count)
        value["match_signal_coverage_pct"] = _ratio(int(value.get("match_signal_task_count") or 0), task_count)
        value["fallback_ratio_pct"] = _ratio(int(value.get("fallback_count") or 0), task_count)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if tasks and records else "FAIL",
        "task_count": len(tasks),
        "record_count": len(records),
        "retrieval_task_count": retrieval_task_count,
        "retrieval_coverage_pct": _ratio(retrieval_task_count, len(records)),
        "match_signal_task_count": match_signal_task_count,
        "match_signal_coverage_pct": _ratio(match_signal_task_count, len(records)),
        "fallback_count": fallback_count,
        "fallback_ratio_pct": _ratio(fallback_count, len(records)),
        "diagnostic_parse_coverage_pct": _ratio(diagnostic_parse_count, len(records)),
        "avg_library_match_count": _mean(library_match_total, len(records)),
        "avg_component_match_count": _mean(component_match_total, len(records)),
        "avg_connector_match_count": _mean(connector_match_total, len(records)),
        "counts_by_library": counts_by_library,
        "sources": {
            "taskset": args.taskset,
            "results": args.results,
        },
        "reasons": [] if tasks and records else ["taskset_or_results_missing"],
    }
    _write_json(args.out, summary)
    _write_markdown(str(args.report_out or _default_md_path(str(args.out))), summary)
    print(json.dumps({"status": summary.get("status"), "retrieval_coverage_pct": summary.get("retrieval_coverage_pct")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

