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
        "# GateForge Large Model Campaign Board",
        "",
        f"- status: `{payload.get('status')}`",
        f"- campaign_phase: `{payload.get('campaign_phase')}`",
        f"- weekly_target_cases: `{payload.get('weekly_target_cases')}`",
        f"- weekly_completed_cases: `{payload.get('weekly_completed_cases')}`",
        f"- target_gap_pressure_index: `{payload.get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{payload.get('model_asset_target_gap_score')}`",
        "",
        "## Action Items",
        "",
    ]
    for row in payload.get("action_items") if isinstance(payload.get("action_items"), list) else []:
        lines.append(f"- `{row}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large-model campaign board from queue/tracker/forecast")
    parser.add_argument("--large-model-failure-queue", required=True)
    parser.add_argument("--pack-execution-tracker", required=True)
    parser.add_argument("--moat-execution-forecast", required=True)
    parser.add_argument("--out", default="artifacts/dataset_large_model_campaign_board/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    queue = _load_json(args.large_model_failure_queue)
    tracker = _load_json(args.pack_execution_tracker)
    forecast = _load_json(args.moat_execution_forecast)

    reasons: list[str] = []
    if not queue:
        reasons.append("large_model_queue_missing")
    if not tracker:
        reasons.append("pack_execution_tracker_missing")
    if not forecast:
        reasons.append("moat_execution_forecast_missing")

    queue_items = _to_int(queue.get("total_queue_items", 0))
    target_gap_pressure = _to_float(forecast.get("target_gap_pressure_index", 0.0))
    target_gap_score = _to_float(forecast.get("model_asset_target_gap_score", 0.0))
    gap_urgency_boost = 0
    if target_gap_score >= 35.0:
        gap_urgency_boost += 2
    if target_gap_pressure < 60.0:
        gap_urgency_boost += 1
    weekly_target = max(2, min(12, queue_items + gap_urgency_boost))

    large_progress = _to_float(tracker.get("large_scale_progress_percent", 0.0))
    completed = max(0, int(round((large_progress / 100.0) * weekly_target)))

    projected = _to_float(forecast.get("projected_moat_score_30d", 0.0))
    phase = "scale_out"
    if projected < 65 or target_gap_score >= 40.0 or target_gap_pressure < 55.0:
        phase = "stabilize"
    elif projected >= 75 and target_gap_score < 25.0 and target_gap_pressure >= 70.0:
        phase = "accelerate"

    action_items: list[str] = []
    if queue_items > 0:
        action_items.append("close_top_2_large_queue_items")
    if large_progress < 40:
        action_items.append("raise_large_model_execution_throughput")
    if phase == "stabilize":
        action_items.append("run_conservative_policy_experiment")
    if phase == "accelerate":
        action_items.append("expand_large_model_case_batch_size")
    if target_gap_score >= 35.0:
        action_items.append("prioritize_high_gap_real_model_intake")
    if target_gap_pressure < 60.0:
        action_items.append("backfill_target_coverage_deficits")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif phase == "stabilize" or large_progress < 40 or target_gap_score >= 40.0 or target_gap_pressure < 60.0:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "campaign_phase": phase,
        "weekly_target_cases": weekly_target,
        "weekly_completed_cases": completed,
        "queue_items": queue_items,
        "large_scale_progress_percent": large_progress,
        "projected_moat_score_30d": projected,
        "target_gap_pressure_index": round(target_gap_pressure, 2),
        "model_asset_target_gap_score": round(target_gap_score, 2),
        "action_items": action_items,
        "reasons": sorted(set(reasons)),
        "sources": {
            "large_model_failure_queue": args.large_model_failure_queue,
            "pack_execution_tracker": args.pack_execution_tracker,
            "moat_execution_forecast": args.moat_execution_forecast,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "campaign_phase": phase, "weekly_target_cases": weekly_target}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
