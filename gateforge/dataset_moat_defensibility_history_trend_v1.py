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


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Moat Defensibility History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- delta_avg_defensibility_score: `{trend.get('delta_avg_defensibility_score')}`",
        f"- delta_pass_rate_pct: `{trend.get('delta_pass_rate_pct')}`",
        f"- delta_publish_ready_streak: `{trend.get('delta_publish_ready_streak')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare moat defensibility history snapshots and emit trend")
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_defensibility_history_trend_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    previous = _load_json(args.previous)
    current = _load_json(args.current)

    reasons: list[str] = []
    if not previous:
        reasons.append("previous_history_missing")
    if not current:
        reasons.append("current_history_missing")

    prev_status = str(previous.get("status") or "UNKNOWN")
    curr_status = str(current.get("status") or "UNKNOWN")

    delta_avg_score = round(_to_float(current.get("avg_defensibility_score", 0.0)) - _to_float(previous.get("avg_defensibility_score", 0.0)), 4)
    delta_pass_rate = round(_to_float(current.get("pass_rate_pct", 0.0)) - _to_float(previous.get("pass_rate_pct", 0.0)), 4)
    delta_streak = round(_to_float(current.get("publish_ready_streak", 0.0)) - _to_float(previous.get("publish_ready_streak", 0.0)), 4)

    alerts: list[str] = []
    if prev_status == "PASS" and curr_status != "PASS":
        alerts.append("defensibility_history_status_worsened")
    if delta_avg_score < 0:
        alerts.append("avg_defensibility_score_decreasing")
    if delta_pass_rate < 0:
        alerts.append("pass_rate_decreasing")
    if delta_streak < 0:
        alerts.append("publish_ready_streak_decreasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "trend": {
            "status_transition": f"{prev_status}->{curr_status}",
            "delta_avg_defensibility_score": delta_avg_score,
            "delta_pass_rate_pct": delta_pass_rate,
            "delta_publish_ready_streak": delta_streak,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {"previous": args.previous, "current": args.current},
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "status_transition": payload['trend']['status_transition']}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
