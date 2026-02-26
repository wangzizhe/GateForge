from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _score(item: dict) -> int:
    pr = str(item.get("priority") or "P2")
    base = {"P0": 90, "P1": 70, "P2": 50, "P3": 35}.get(pr, 40)
    reason = str(item.get("reason") or "")
    if "regression" in reason:
        base += 10
    if "distribution_drift" in reason:
        base += 8
    if "model_scale" in reason:
        base += 6
    return min(100, base)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Large Model Failure Queue",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_queue_items: `{payload.get('total_queue_items')}`",
        f"- p0_items: `{payload.get('p0_items')}`",
        "",
        "## Top Queue",
        "",
    ]
    for row in (payload.get("queue") if isinstance(payload.get("queue"), list) else [])[:10]:
        lines.append(f"- `{row.get('queue_id')}` score=`{row.get('priority_score')}` reason=`{row.get('reason')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prioritize large-model failure queue from backlog and registry signals")
    parser.add_argument("--blind-spot-backlog", required=True)
    parser.add_argument("--failure-corpus-registry-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_large_model_failure_queue/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    backlog = _load_json(args.blind_spot_backlog)
    registry = _load_json(args.failure_corpus_registry_summary)

    reasons: list[str] = []
    tasks = backlog.get("tasks") if isinstance(backlog.get("tasks"), list) else []
    queue: list[dict] = []

    for i, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "")
        is_large = ".large" in task_id or "large" in str(task.get("title") or "").lower()
        if not is_large:
            continue
        row = {
            "queue_id": f"largeq.{i:03d}",
            "source_task_id": task_id,
            "priority": str(task.get("priority") or "P2"),
            "reason": str(task.get("reason") or "unknown"),
            "priority_score": _score(task),
            "state": "READY",
        }
        queue.append(row)

    missing_scales = registry.get("missing_model_scales") if isinstance(registry.get("missing_model_scales"), list) else []
    if "large" in [str(x) for x in missing_scales]:
        queue.append(
            {
                "queue_id": "largeq.registry.backfill",
                "source_task_id": "registry.missing_model_scale.large",
                "priority": "P0",
                "reason": "registry_missing_model_scale",
                "priority_score": 95,
                "state": "READY",
            }
        )

    queue.sort(key=lambda x: (-_to_int(x.get("priority_score", 0)), str(x.get("queue_id") or "")))

    if not backlog:
        reasons.append("backlog_missing")
    if not queue:
        reasons.append("no_large_model_queue_items")

    status = "PASS"
    if reasons:
        status = "NEEDS_REVIEW"
    if "backlog_missing" in reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_queue_items": len(queue),
        "p0_items": len([x for x in queue if str(x.get("priority") or "") == "P0"]),
        "queue": queue,
        "reasons": sorted(set(reasons)),
        "sources": {
            "blind_spot_backlog": args.blind_spot_backlog,
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_queue_items": len(queue)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
