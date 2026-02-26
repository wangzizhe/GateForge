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


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _priority_rank(priority: str) -> int:
    ranks = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return ranks.get(priority, 4)


def _estimate_delta(points: int, size_hint: str) -> float:
    scale = 1.0
    if size_hint == "large":
        scale = 1.35
    elif size_hint == "medium":
        scale = 1.15
    return round(points * 0.6 * scale, 2)


def _plan_rows(backlog: dict, registry: dict, moat: dict) -> tuple[list[dict], list[str]]:
    tasks = backlog.get("tasks") if isinstance(backlog.get("tasks"), list) else []
    missing_scales = registry.get("missing_model_scales") if isinstance(registry.get("missing_model_scales"), list) else []

    rows: list[dict] = []
    reasons: list[str] = []

    for index, task in enumerate(tasks[:20], start=1):
        task_id = str(task.get("task_id") or f"task_{index}")
        priority = str(task.get("priority") or "P2")
        reason = str(task.get("reason") or "unknown")
        title = str(task.get("title") or task_id)
        score = 12 - (_priority_rank(priority) * 3)

        size_hint = "small"
        if ".large" in task_id:
            size_hint = "large"
        elif ".medium" in task_id:
            size_hint = "medium"

        lane = "quick"
        if size_hint == "large" or priority == "P0":
            lane = "extended"
        elif priority == "P1":
            lane = "standard"

        rows.append(
            {
                "plan_id": f"coverage.plan.{index:03d}",
                "source_task_id": task_id,
                "priority": priority,
                "lane": lane,
                "focus": reason,
                "title": title,
                "size_hint": size_hint,
                "expected_moat_delta": _estimate_delta(score, size_hint),
            }
        )

    for scale in missing_scales:
        scale_name = str(scale)
        rows.append(
            {
                "plan_id": f"coverage.scale.{scale_name}",
                "source_task_id": f"registry.missing_model_scale.{scale_name}",
                "priority": "P0" if scale_name == "large" else "P1",
                "lane": "extended" if scale_name == "large" else "standard",
                "focus": "registry_missing_model_scale",
                "title": f"Backfill {scale_name} model evidence cases",
                "size_hint": scale_name,
                "expected_moat_delta": _estimate_delta(11 if scale_name == "large" else 8, scale_name),
            }
        )

    if not rows:
        reasons.append("no_backlog_tasks_or_registry_gaps")

    moat_score = _to_float(((moat.get("metrics") or {}).get("moat_score") if isinstance(moat.get("metrics"), dict) else 0.0))
    if moat_score < 60.0:
        reasons.append("moat_score_below_target")

    dedup: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("source_task_id") or row.get("plan_id") or "")
        if not key:
            continue
        if key not in dedup or _to_float(row.get("expected_moat_delta", 0.0)) > _to_float(dedup[key].get("expected_moat_delta", 0.0)):
            dedup[key] = row

    ordered = sorted(
        dedup.values(),
        key=lambda x: (
            _priority_rank(str(x.get("priority") or "P3")),
            -_to_float(x.get("expected_moat_delta", 0.0)),
            str(x.get("source_task_id") or ""),
        ),
    )
    return ordered, sorted(set(reasons))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# GateForge Failure Coverage Planner",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_plan_items: `{payload.get('total_plan_items')}`",
        f"- expected_moat_delta_total: `{payload.get('expected_moat_delta_total')}`",
        f"- ready_large_model_tracks: `{payload.get('ready_large_model_tracks')}`",
        "",
        "## Top Plan Items",
        "",
    ]

    plan_rows = payload.get("plan") if isinstance(payload.get("plan"), list) else []
    if plan_rows:
        for row in plan_rows[:15]:
            lines.append(
                f"- `{row.get('priority')}` `{row.get('plan_id')}` lane=`{row.get('lane')}` expected_moat_delta=`{row.get('expected_moat_delta')}`"
            )
    else:
        lines.append("- `none`")

    lines.extend(["", "## Reasons", ""])
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")

    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate executable failure coverage plan from backlog and moat signals")
    parser.add_argument("--blind-spot-backlog", required=True)
    parser.add_argument("--failure-corpus-registry-summary", default=None)
    parser.add_argument("--moat-trend-snapshot", default=None)
    parser.add_argument("--out", default="artifacts/dataset_failure_coverage_planner/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    backlog = _load_json(args.blind_spot_backlog)
    registry = _load_json(args.failure_corpus_registry_summary)
    moat = _load_json(args.moat_trend_snapshot)

    rows, reasons = _plan_rows(backlog, registry, moat)

    large_tracks = len([x for x in rows if str(x.get("size_hint") or "") == "large"])
    total_delta = round(sum(_to_float(x.get("expected_moat_delta", 0.0)) for x in rows), 2)

    status = "PASS"
    if not backlog:
        status = "FAIL"
        reasons = sorted(set(reasons + ["backlog_missing"]))
    elif rows:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_plan_items": len(rows),
        "ready_large_model_tracks": large_tracks,
        "expected_moat_delta_total": total_delta,
        "plan": rows,
        "reasons": reasons,
        "sources": {
            "blind_spot_backlog": args.blind_spot_backlog,
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
            "moat_trend_snapshot": args.moat_trend_snapshot,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_plan_items": len(rows), "expected_moat_delta_total": total_delta}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
