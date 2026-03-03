from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


STAGE_BY_FAILURE_TYPE = {
    "simulate_error": "simulate",
    "model_check_error": "check",
    "semantic_regression": "simulate",
    "numerical_instability": "simulate",
    "constraint_violation": "check",
}


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_") or default


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _extract_rows(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key) if isinstance(payload.get(key), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _load_matrix(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Coverage Gap Backfill v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- p0_tasks: `{payload.get('p0_tasks')}`",
        f"- medium_tasks: `{payload.get('medium_tasks')}`",
        f"- large_tasks: `{payload.get('large_tasks')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mutation coverage backfill tasks from validation matrix v2")
    parser.add_argument("--validation-matrix-v2-summary", required=True)
    parser.add_argument("--failure-distribution-stability-guard-summary", default=None)
    parser.add_argument("--max-tasks", type=int, default=30)
    parser.add_argument("--tasks-out", default="artifacts/dataset_mutation_coverage_gap_backfill_v1/tasks.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_coverage_gap_backfill_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    summary = _load_json(args.validation_matrix_v2_summary)
    guard = _load_json(args.failure_distribution_stability_guard_summary)
    reasons: list[str] = []
    if not summary:
        reasons.append("validation_matrix_v2_summary_missing")

    matrix_path = str(summary.get("matrix_path") or "").strip()
    matrix = _load_matrix(matrix_path) if matrix_path else {}
    if matrix_path and not matrix:
        reasons.append("validation_matrix_payload_missing")

    type_conf = matrix.get("type_confusion") if isinstance(matrix.get("type_confusion"), dict) else {}
    medium_type_rows = _extract_rows(type_conf, "medium")
    large_type_rows = _extract_rows(type_conf, "large")
    other_type_rows = _extract_rows(type_conf, "other")

    backlog_tasks: list[dict] = []

    def _add_tasks(rows: list[dict], scale: str) -> None:
        expected_total: dict[str, int] = {}
        matched_total: dict[str, int] = {}
        for row in rows:
            expected = _slug(row.get("expected"), default="unknown")
            observed = _slug(row.get("observed"), default="unknown")
            count = _to_int(row.get("count", 0))
            expected_total[expected] = expected_total.get(expected, 0) + count
            if expected == observed:
                matched_total[expected] = matched_total.get(expected, 0) + count
        for expected, total in sorted(expected_total.items()):
            matched = matched_total.get(expected, 0)
            gap = max(0, total - matched)
            if gap <= 0:
                continue
            stage = STAGE_BY_FAILURE_TYPE.get(expected, "simulate")
            priority = "P0" if scale == "large" else "P1"
            backlog_tasks.append(
                {
                    "task_id": f"backfill.{scale}.{expected}.{stage}",
                    "priority": priority,
                    "target_scale": scale,
                    "failure_type": expected,
                    "expected_stage": stage,
                    "gap_count": gap,
                    "planned_actions": [
                        "increase_recipe_seed_count",
                        "prioritize_mismatch_operator_family",
                    ],
                    "reason": "validation_confusion_gap",
                }
            )

    _add_tasks(medium_type_rows, "medium")
    _add_tasks(large_type_rows, "large")
    _add_tasks(other_type_rows, "other")

    guard_alerts = guard.get("alerts") if isinstance(guard.get("alerts"), list) else []
    if guard_alerts:
        backlog_tasks.append(
            {
                "task_id": "backfill.distribution_guard",
                "priority": "P0",
                "target_scale": "multi",
                "failure_type": "multi",
                "expected_stage": "multi",
                "gap_count": len(guard_alerts),
                "planned_actions": ["rebalance_failure_type_mix", "increase_long_tail_types"],
                "reason": "distribution_guard_alerts",
            }
        )

    backlog_tasks.sort(key=lambda x: (str(x.get("priority") or "P9"), -_to_int(x.get("gap_count", 0)), str(x.get("task_id") or "")))
    backlog_tasks = backlog_tasks[: max(1, int(args.max_tasks))]

    status = "PASS"
    alerts: list[str] = []
    if reasons:
        status = "FAIL"
    elif backlog_tasks:
        status = "NEEDS_REVIEW"
        alerts.append("coverage_backfill_tasks_generated")

    _write_json(
        args.tasks_out,
        {
            "schema_version": "mutation_coverage_gap_backfill_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "tasks": backlog_tasks,
        },
    )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(backlog_tasks),
        "p0_tasks": len([x for x in backlog_tasks if str(x.get("priority") or "") == "P0"]),
        "medium_tasks": len([x for x in backlog_tasks if str(x.get("target_scale") or "") == "medium"]),
        "large_tasks": len([x for x in backlog_tasks if str(x.get("target_scale") or "") == "large"]),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "tasks_path": args.tasks_out,
        "sources": {
            "validation_matrix_v2_summary": args.validation_matrix_v2_summary,
            "failure_distribution_stability_guard_summary": args.failure_distribution_stability_guard_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_tasks": len(backlog_tasks)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
