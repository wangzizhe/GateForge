from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


TARGET_FAILURE_TYPES = [
    "simulate_error",
    "model_check_error",
    "semantic_regression",
    "numerical_instability",
    "constraint_violation",
]


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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _extract_cases(db: dict) -> list[dict]:
    rows = db.get("cases") if isinstance(db.get("cases"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_queue(queue_payload: dict) -> list[dict]:
    rows = queue_payload.get("queue") if isinstance(queue_payload.get("queue"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _compute_required_additional_large(total_cases: int, large_cases: int, target_share_pct: float) -> int:
    if total_cases <= 0:
        return 0
    target = max(0.0, min(0.99, target_share_pct / 100.0))
    if target <= 0:
        return 0
    current_share = large_cases / total_cases
    if current_share >= target:
        return 0
    required = ((target * total_cases) - large_cases) / (1.0 - target)
    return max(0, int(math.ceil(required)))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Large Coverage Push v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- current_large_share_pct: `{payload.get('current_large_share_pct')}`",
        f"- target_large_share_pct: `{payload.get('target_large_share_pct')}`",
        f"- additional_large_cases_required: `{payload.get('additional_large_cases_required')}`",
        f"- push_target_large_cases: `{payload.get('push_target_large_cases')}`",
        "",
        "## Missing Large Failure Types",
        "",
    ]
    missing = payload.get("missing_large_failure_types")
    if isinstance(missing, list) and missing:
        for item in missing:
            lines.append(f"- `{item}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create execution plan to push large-model failure coverage")
    parser.add_argument("--failure-corpus-db", required=True)
    parser.add_argument("--model-scale-ladder-summary", required=True)
    parser.add_argument("--large-model-failure-queue", default=None)
    parser.add_argument("--target-large-share-pct", type=float, default=25.0)
    parser.add_argument("--min-new-large-cases", type=int, default=5)
    parser.add_argument("--out", default="artifacts/dataset_large_coverage_push_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    db = _load_json(args.failure_corpus_db)
    ladder = _load_json(args.model_scale_ladder_summary)
    queue_payload = _load_json(args.large_model_failure_queue)

    reasons: list[str] = []
    if not db:
        reasons.append("failure_corpus_db_missing")
    if not ladder:
        reasons.append("model_scale_ladder_summary_missing")

    cases = _extract_cases(db)
    total_cases = len(cases)
    large_cases = [x for x in cases if _slug(x.get("model_scale")) == "large"]
    large_count = len(large_cases)
    current_large_share_pct = round((large_count / total_cases) * 100.0, 2) if total_cases > 0 else 0.0

    large_failure_type_counts: dict[str, int] = {}
    for row in large_cases:
        ft = _slug(row.get("failure_type"), default="unknown")
        large_failure_type_counts[ft] = large_failure_type_counts.get(ft, 0) + 1

    missing_large_failure_types = [x for x in TARGET_FAILURE_TYPES if large_failure_type_counts.get(x, 0) <= 0]
    required_additional = _compute_required_additional_large(
        total_cases=total_cases,
        large_cases=large_count,
        target_share_pct=float(args.target_large_share_pct),
    )

    large_ready = bool(ladder.get("large_ready", False))
    push_floor = max(0, int(args.min_new_large_cases))
    push_target = max(required_additional, push_floor if not large_ready else 0)
    if missing_large_failure_types:
        push_target = max(push_target, len(missing_large_failure_types))

    queue_rows = _extract_queue(queue_payload)
    queue_top = queue_rows[: min(12, len(queue_rows))]

    recommended_actions: list[dict] = []
    for i, ft in enumerate(missing_large_failure_types, start=1):
        recommended_actions.append(
            {
                "action_id": f"coverage.large.ft.{i:03d}",
                "action_type": "synthesize_large_failure_case",
                "failure_type": ft,
                "priority": "P0" if i <= 2 else "P1",
            }
        )

    for i, row in enumerate(queue_top, start=1):
        recommended_actions.append(
            {
                "action_id": f"coverage.large.queue.{i:03d}",
                "action_type": "execute_large_queue_item",
                "queue_id": str(row.get("queue_id") or ""),
                "priority": str(row.get("priority") or "P2"),
                "reason": str(row.get("reason") or ""),
            }
        )

    alerts: list[str] = []
    if total_cases == 0:
        alerts.append("failure_corpus_empty")
    if current_large_share_pct < float(args.target_large_share_pct):
        alerts.append("large_share_below_target")
    if missing_large_failure_types:
        alerts.append("large_failure_type_coverage_gaps")
    if not large_ready:
        alerts.append("large_scale_not_ready")
    if not queue_rows and push_target > 0:
        alerts.append("large_queue_missing_or_empty")

    status = "PASS"
    if "failure_corpus_db_missing" in reasons or "model_scale_ladder_summary_missing" in reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "current_large_share_pct": current_large_share_pct,
        "target_large_share_pct": float(args.target_large_share_pct),
        "additional_large_cases_required": required_additional,
        "push_target_large_cases": push_target,
        "large_ready": large_ready,
        "total_cases": total_cases,
        "large_case_count": large_count,
        "missing_large_failure_types": missing_large_failure_types,
        "large_failure_type_counts": large_failure_type_counts,
        "recommended_actions": recommended_actions,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_corpus_db": args.failure_corpus_db,
            "model_scale_ladder_summary": args.model_scale_ladder_summary,
            "large_model_failure_queue": args.large_model_failure_queue,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)

    print(
        json.dumps(
            {
                "status": status,
                "current_large_share_pct": current_large_share_pct,
                "push_target_large_cases": push_target,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
