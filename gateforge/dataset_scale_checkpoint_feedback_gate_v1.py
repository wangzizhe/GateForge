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
        "# GateForge Scale Checkpoint Feedback Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- feedback_score: `{payload.get('feedback_score')}`",
        f"- adjusted_checkpoint_status: `{payload.get('adjusted_checkpoint_status')}`",
        f"- focus_next_week_count: `{payload.get('focus_next_week_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply backlog/velocity feedback to weekly checkpoint status")
    parser.add_argument("--weekly-scale-milestone-checkpoint-summary", required=True)
    parser.add_argument("--scale-action-backlog-history-summary", required=True)
    parser.add_argument("--scale-action-backlog-trend-summary", required=True)
    parser.add_argument("--scale-velocity-forecast-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_scale_checkpoint_feedback_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    checkpoint = _load_json(args.weekly_scale_milestone_checkpoint_summary)
    history = _load_json(args.scale_action_backlog_history_summary)
    trend = _load_json(args.scale_action_backlog_trend_summary)
    velocity = _load_json(args.scale_velocity_forecast_summary)
    reasons: list[str] = []
    if not checkpoint:
        reasons.append("weekly_scale_milestone_checkpoint_summary_missing")
    if not history:
        reasons.append("scale_action_backlog_history_summary_missing")
    if not trend:
        reasons.append("scale_action_backlog_trend_summary_missing")
    if not velocity:
        reasons.append("scale_velocity_forecast_summary_missing")

    checkpoint_score = _to_float(checkpoint.get("milestone_score", 0.0))
    avg_p0 = _to_float(history.get("avg_total_p0_actions", 0.0))
    delta_p0 = _to_float((trend.get("trend") or {}).get("delta_avg_total_p0_actions"))
    on_track = bool(velocity.get("on_track_within_horizon"))
    model_weeks = _to_int(velocity.get("model_gap_weeks_to_close", 999))
    mutation_weeks = _to_int(velocity.get("mutation_gap_weeks_to_close", 999))

    feedback_score = checkpoint_score
    feedback_score -= min(20.0, avg_p0 * 4.0)
    if delta_p0 > 0:
        feedback_score -= min(10.0, delta_p0 * 5.0)
    if not on_track:
        feedback_score -= 8.0
    feedback_score = round(max(0.0, min(100.0, feedback_score)), 2)

    adjusted_status = "PASS"
    if feedback_score < 60.0:
        adjusted_status = "FAIL"
    elif feedback_score < 75.0 or not on_track:
        adjusted_status = "NEEDS_REVIEW"

    focus: list[str] = []
    if model_weeks > 12:
        focus.append("accelerate_model_intake_velocity")
    if mutation_weeks > 12:
        focus.append("accelerate_reproducible_mutation_velocity")
    if avg_p0 >= 2.0 or delta_p0 > 0:
        focus.append("close_backlog_p0_actions")
    if str(checkpoint.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        focus.append("resolve_checkpoint_alerts")

    alerts: list[str] = []
    if adjusted_status != "PASS":
        alerts.append("checkpoint_feedback_not_pass")
    if not on_track:
        alerts.append("velocity_not_on_track")
    if avg_p0 >= 2.0:
        alerts.append("avg_p0_backlog_high")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "feedback_score": feedback_score,
        "adjusted_checkpoint_status": adjusted_status,
        "focus_next_week_count": len(focus),
        "focus_next_week": focus[:5],
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "checkpoint_score": checkpoint_score,
            "avg_total_p0_actions": avg_p0,
            "delta_avg_total_p0_actions": delta_p0,
            "velocity_on_track": on_track,
            "model_gap_weeks_to_close": model_weeks,
            "mutation_gap_weeks_to_close": mutation_weeks,
        },
        "sources": {
            "weekly_scale_milestone_checkpoint_summary": args.weekly_scale_milestone_checkpoint_summary,
            "scale_action_backlog_history_summary": args.scale_action_backlog_history_summary,
            "scale_action_backlog_trend_summary": args.scale_action_backlog_trend_summary,
            "scale_velocity_forecast_summary": args.scale_velocity_forecast_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "feedback_score": feedback_score, "adjusted_checkpoint_status": adjusted_status}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
