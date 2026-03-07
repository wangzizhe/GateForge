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


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _safe_float(value: object, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _compute_from_results(run_results: dict) -> dict:
    rows = run_results.get("records") if isinstance(run_results.get("records"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    total = len(rows)
    success = sum(1 for row in rows if bool(row.get("passed", False)))
    times = [
        float(row.get("time_to_pass_sec"))
        for row in rows
        if isinstance(row.get("time_to_pass_sec"), (int, float))
    ]
    rounds = [
        int(row.get("rounds_used"))
        for row in rows
        if isinstance(row.get("rounds_used"), (int, float)) and bool(row.get("passed", False))
    ]
    regression_count = 0
    physics_fail_count = 0
    for row in rows:
        hard = row.get("hard_checks") if isinstance(row.get("hard_checks"), dict) else {}
        if not bool(hard.get("regression_pass", True)):
            regression_count += 1
        if not bool(hard.get("physics_contract_pass", True)):
            physics_fail_count += 1
    median_time = None
    if times:
        s = sorted(times)
        n = len(s)
        if n % 2 == 1:
            median_time = s[n // 2]
        else:
            median_time = round((s[(n // 2) - 1] + s[n // 2]) / 2.0, 6)
    median_rounds = None
    if rounds:
        s = sorted(rounds)
        n = len(s)
        if n % 2 == 1:
            median_rounds = float(s[n // 2])
        else:
            median_rounds = round((s[(n // 2) - 1] + s[n // 2]) / 2.0, 6)
    success_at_k = round((float(success) * 100.0 / float(total)), 4) if total > 0 else 0.0
    return {
        "total_tasks": total,
        "success_count": success,
        "success_at_k_pct": success_at_k,
        "median_time_to_pass_sec": median_time,
        "median_repair_rounds": median_rounds,
        "regression_count": regression_count,
        "physics_fail_count": physics_fail_count,
    }


def _metrics(run_summary: dict, run_results: dict) -> dict:
    fallback = _compute_from_results(run_results)
    out = dict(fallback)
    for key in (
        "total_tasks",
        "success_count",
        "success_at_k_pct",
        "median_time_to_pass_sec",
        "median_repair_rounds",
        "regression_count",
        "physics_fail_count",
    ):
        if key in run_summary:
            value = run_summary.get(key)
            if key in {"total_tasks", "success_count", "regression_count", "physics_fail_count"}:
                out[key] = _safe_int(value, out[key])
            else:
                out[key] = _safe_float(value, out[key])
    return out


def _delta(after: float | None, before: float | None) -> float | None:
    if after is None or before is None:
        return None
    return round(float(after) - float(before), 4)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    before = payload.get("before_metrics") if isinstance(payload.get("before_metrics"), dict) else {}
    after = payload.get("after_metrics") if isinstance(payload.get("after_metrics"), dict) else {}
    delta = payload.get("delta") if isinstance(payload.get("delta"), dict) else {}
    queue = payload.get("focus_queue_top2") if isinstance(payload.get("focus_queue_top2"), list) else []
    lines = [
        "# Agent Modelica Live Focus Boost Compare v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- reasons: `{payload.get('reasons')}`",
        "",
        "## Metrics",
        "",
        f"- before_success_at_k_pct: `{before.get('success_at_k_pct')}`",
        f"- after_success_at_k_pct: `{after.get('success_at_k_pct')}`",
        f"- delta_success_at_k_pct: `{delta.get('success_at_k_pct')}`",
        f"- before_regression_count: `{before.get('regression_count')}`",
        f"- after_regression_count: `{after.get('regression_count')}`",
        f"- delta_regression_count: `{delta.get('regression_count')}`",
        f"- before_physics_fail_count: `{before.get('physics_fail_count')}`",
        f"- after_physics_fail_count: `{after.get('physics_fail_count')}`",
        f"- delta_physics_fail_count: `{delta.get('physics_fail_count')}`",
        "",
        "## Focus Top2",
        "",
    ]
    if queue:
        for row in queue:
            lines.append(
                f"- `{row.get('rank')}` `{row.get('failure_type')}` gate=`{row.get('gate_break_reason')}` "
                f"priority=`{row.get('priority_score')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare before/after live focus reruns for modelica electrical tasks")
    parser.add_argument("--before-run-summary", required=True)
    parser.add_argument("--before-run-results", required=True)
    parser.add_argument("--after-run-summary", required=True)
    parser.add_argument("--after-run-results", required=True)
    parser.add_argument("--focus-queue", default="")
    parser.add_argument("--focus-templates", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_live_focus_boost_compare_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    before_summary = _load_json(args.before_run_summary)
    before_results = _load_json(args.before_run_results)
    after_summary = _load_json(args.after_run_summary)
    after_results = _load_json(args.after_run_results)
    focus_queue = _load_json(args.focus_queue) if str(args.focus_queue).strip() else {}
    focus_templates = _load_json(args.focus_templates) if str(args.focus_templates).strip() else {}

    before = _metrics(before_summary, before_results)
    after = _metrics(after_summary, after_results)
    delta = {
        "success_at_k_pct": _delta(_safe_float(after.get("success_at_k_pct")), _safe_float(before.get("success_at_k_pct"))),
        "median_time_to_pass_sec": _delta(_safe_float(after.get("median_time_to_pass_sec")), _safe_float(before.get("median_time_to_pass_sec"))),
        "median_repair_rounds": _delta(_safe_float(after.get("median_repair_rounds")), _safe_float(before.get("median_repair_rounds"))),
        "regression_count": _delta(_safe_float(after.get("regression_count")), _safe_float(before.get("regression_count"))),
        "physics_fail_count": _delta(_safe_float(after.get("physics_fail_count")), _safe_float(before.get("physics_fail_count"))),
    }

    reasons: list[str] = []
    if _safe_float(after.get("success_at_k_pct"), 0.0) < _safe_float(before.get("success_at_k_pct"), 0.0):
        reasons.append("success_at_k_degraded")
    if _safe_int(after.get("regression_count"), 0) > _safe_int(before.get("regression_count"), 0):
        reasons.append("regression_count_increased")
    if _safe_int(after.get("physics_fail_count"), 0) > _safe_int(before.get("physics_fail_count"), 0):
        reasons.append("physics_fail_count_increased")

    status = "PASS"
    if reasons:
        if "regression_count_increased" in reasons or "physics_fail_count_increased" in reasons:
            status = "FAIL"
        else:
            status = "NEEDS_REVIEW"

    queue_rows = focus_queue.get("queue") if isinstance(focus_queue.get("queue"), list) else []
    template_rows = focus_templates.get("templates") if isinstance(focus_templates.get("templates"), list) else []
    out = {
        "schema_version": "agent_modelica_live_focus_boost_compare_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reasons": reasons,
        "before_metrics": before,
        "after_metrics": after,
        "delta": delta,
        "focus_queue_top2": [x for x in queue_rows[:2] if isinstance(x, dict)],
        "focus_template_top2": [x for x in template_rows[:2] if isinstance(x, dict)],
        "sources": {
            "before_run_summary": args.before_run_summary,
            "before_run_results": args.before_run_results,
            "after_run_summary": args.after_run_summary,
            "after_run_results": args.after_run_results,
            "focus_queue": args.focus_queue if str(args.focus_queue).strip() else None,
            "focus_templates": args.focus_templates if str(args.focus_templates).strip() else None,
        },
    }
    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(
        json.dumps(
            {
                "status": out.get("status"),
                "delta_success_at_k_pct": delta.get("success_at_k_pct"),
                "delta_regression_count": delta.get("regression_count"),
                "delta_physics_fail_count": delta.get("physics_fail_count"),
            }
        )
    )


if __name__ == "__main__":
    main()
