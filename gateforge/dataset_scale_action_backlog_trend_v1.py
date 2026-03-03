from __future__ import annotations

import argparse
import json
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
        "# GateForge Scale Action Backlog Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- delta_avg_total_actions: `{trend.get('delta_avg_total_actions')}`",
        f"- delta_avg_total_p0_actions: `{trend.get('delta_avg_total_p0_actions')}`",
        f"- delta_avg_checkpoint_score: `{trend.get('delta_avg_checkpoint_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare scale action backlog history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_scale_action_backlog_history_v1/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)
    reasons: list[str] = []
    if not current:
        reasons.append("current_summary_missing")
    if not previous:
        reasons.append("previous_summary_missing")

    trend = {
        "status_transition": f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}",
        "delta_avg_total_actions": round(_to_float(current.get("avg_total_actions")) - _to_float(previous.get("avg_total_actions")), 4),
        "delta_avg_total_p0_actions": round(
            _to_float(current.get("avg_total_p0_actions")) - _to_float(previous.get("avg_total_p0_actions")),
            4,
        ),
        "delta_avg_checkpoint_score": round(
            _to_float(current.get("avg_checkpoint_score")) - _to_float(previous.get("avg_checkpoint_score")),
            4,
        ),
    }

    alerts: list[str] = []
    if trend["status_transition"] in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("action_backlog_history_status_worsened")
    if trend["delta_avg_total_actions"] > 0:
        alerts.append("avg_total_actions_increasing")
    if trend["delta_avg_total_p0_actions"] > 0:
        alerts.append("avg_total_p0_actions_increasing")
    if trend["delta_avg_checkpoint_score"] < 0:
        alerts.append("avg_checkpoint_score_decreasing")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {"status": status, "trend": {**trend, "alerts": alerts}, "alerts": alerts, "reasons": sorted(set(reasons))}
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
