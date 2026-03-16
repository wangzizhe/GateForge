from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_unknown_library_evidence_v1 import _detect_source_unstable_models


SCHEMA_VERSION = "agent_modelica_curated_hard_unseen_baseline_summary_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _task_index(taskset_payload: dict) -> dict[str, dict]:
    tasks = [row for row in (taskset_payload.get("tasks") or []) if isinstance(row, dict)]
    return {str(task.get("task_id") or "").strip(): task for task in tasks if str(task.get("task_id") or "").strip()}


def _task_bucket_value(task: dict, bucket: str) -> str:
    source_meta = task.get("source_meta") if isinstance(task.get("source_meta"), dict) else {}
    if bucket == "seen_risk_band":
        return str(task.get("seen_risk_band") or source_meta.get("seen_risk_band") or "unknown").strip().lower()
    if bucket == "source_type":
        return str(task.get("source_type") or source_meta.get("source_type") or "unknown").strip().lower()
    return "unknown"


def _success_by_bucket(taskset_payload: dict, results_payload: dict, bucket: str) -> dict[str, dict]:
    task_map = _task_index(taskset_payload)
    counts: dict[str, dict] = {}
    for record in [row for row in (results_payload.get("records") or []) if isinstance(row, dict)]:
        task = task_map.get(str(record.get("task_id") or "").strip(), {})
        bucket_value = _task_bucket_value(task, bucket)
        row = counts.setdefault(bucket_value, {"task_count": 0, "success_count": 0})
        row["task_count"] = int(row.get("task_count") or 0) + 1
        if bool(record.get("passed")):
            row["success_count"] = int(row.get("success_count") or 0) + 1
    for row in counts.values():
        row["success_at_k_pct"] = _ratio(int(row.get("success_count") or 0), int(row.get("task_count") or 0))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize curated hard-unseen baseline results")
    parser.add_argument("--challenge-summary", required=True)
    parser.add_argument("--baseline-summary", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_curated_hard_unseen_live_evidence_v1/hard_unseen_baseline_summary.json")
    parser.add_argument("--source-unstable-exclusions-out", default="")
    args = parser.parse_args()

    challenge = _load_json(args.challenge_summary)
    baseline_summary = _load_json(args.baseline_summary)
    baseline_results = _load_json(args.baseline_results)
    taskset_path = str(challenge.get("taskset_frozen_path") or "").strip()
    taskset = _load_json(taskset_path)
    source_unstable = _detect_source_unstable_models(taskset, baseline_results)
    counts_by_seen_risk_band = challenge.get("counts_by_seen_risk_band") if isinstance(challenge.get("counts_by_seen_risk_band"), dict) else {}
    counts_by_source_type = challenge.get("counts_by_source_type") if isinstance(challenge.get("counts_by_source_type"), dict) else {}
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": str(baseline_summary.get("status") or "FAIL"),
        "total_tasks": int(challenge.get("total_tasks") or 0),
        "success_count": int(baseline_summary.get("success_count") or 0),
        "success_at_k_pct": float(baseline_summary.get("success_at_k_pct") or 0.0),
        "counts_by_library": challenge.get("counts_by_library") if isinstance(challenge.get("counts_by_library"), dict) else {},
        "counts_by_seen_risk_band": counts_by_seen_risk_band,
        "counts_by_source_type": counts_by_source_type,
        "success_by_seen_risk_band": _success_by_bucket(taskset, baseline_results, "seen_risk_band"),
        "success_by_source_type": _success_by_bucket(taskset, baseline_results, "source_type"),
        "source_unstable_summary": source_unstable,
        "sources": {
            "challenge_summary": args.challenge_summary,
            "baseline_summary": args.baseline_summary,
            "baseline_results": args.baseline_results,
        },
    }
    _write_json(args.out, summary)
    exclusions_out = str(args.source_unstable_exclusions_out or "").strip() or str(Path(args.out).with_name("source_unstable_exclusions.json"))
    _write_json(
        exclusions_out,
        {
            "schema_version": "agent_modelica_curated_hard_unseen_source_unstable_exclusions_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "qualified_model_names": source_unstable.get("qualified_model_names"),
            "model_ids": source_unstable.get("model_ids"),
            "library_ids": source_unstable.get("library_ids"),
            "task_ids": source_unstable.get("task_ids"),
            "counts_by_library": source_unstable.get("counts_by_library"),
            "models": source_unstable.get("models"),
            "sources": {"taskset": taskset_path, "baseline_results": args.baseline_results},
        },
    )
    print(json.dumps({"status": summary.get("status"), "success_count": summary.get("success_count"), "total_tasks": summary.get("total_tasks")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
