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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Pack Execution Tracker",
        "",
        f"- status: `{payload.get('status')}`",
        f"- progress_percent: `{payload.get('progress_percent')}`",
        f"- completed_cases: `{payload.get('completed_cases')}`",
        f"- target_cases: `{payload.get('target_cases')}`",
        f"- large_scale_progress_percent: `{payload.get('large_scale_progress_percent')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    if reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Track execution progress of modelica failure pack plan")
    parser.add_argument("--modelica-failure-pack-plan", required=True)
    parser.add_argument("--executed-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_pack_execution_tracker/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    plan = _load_json(args.modelica_failure_pack_plan)
    executed = _load_json(args.executed_summary)

    reasons: list[str] = []
    if not plan:
        reasons.append("pack_plan_missing")
    if not executed:
        reasons.append("executed_summary_missing")

    scale_plan = plan.get("scale_plan") if isinstance(plan.get("scale_plan"), list) else []
    executed_scales = executed.get("scale_completed") if isinstance(executed.get("scale_completed"), dict) else {}

    target_total = _to_int(plan.get("total_target_new_cases", 0))
    completed_total = _to_int(executed.get("completed_cases", 0))
    if completed_total == 0 and executed_scales:
        completed_total = sum(_to_int(v) for v in executed_scales.values())

    progress = round((completed_total / target_total) * 100, 2) if target_total > 0 else 0.0

    large_target = 0
    for row in scale_plan:
        if isinstance(row, dict) and str(row.get("scale") or "") == "large":
            large_target = _to_int(row.get("target_new_cases", 0))
            break
    large_done = _to_int(executed_scales.get("large", 0))
    large_progress = round((large_done / large_target) * 100, 2) if large_target > 0 else 0.0

    blocked_count = _to_int(executed.get("blocked_cases", 0))
    if progress < 40.0:
        reasons.append("overall_progress_low")
    if large_target > 0 and large_progress < 30.0:
        reasons.append("large_scale_progress_low")
    if blocked_count > 0:
        reasons.append("blocked_cases_present")

    status = "PASS"
    if reasons:
        status = "NEEDS_REVIEW"
    if "pack_plan_missing" in reasons or "executed_summary_missing" in reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target_cases": target_total,
        "completed_cases": completed_total,
        "blocked_cases": blocked_count,
        "progress_percent": progress,
        "large_scale_target_cases": large_target,
        "large_scale_completed_cases": large_done,
        "large_scale_progress_percent": large_progress,
        "reasons": sorted(set(reasons)),
        "sources": {
            "modelica_failure_pack_plan": args.modelica_failure_pack_plan,
            "executed_summary": args.executed_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "progress_percent": progress, "large_scale_progress_percent": large_progress}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
