from __future__ import annotations

import argparse
import json
import math
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


def _weeks_to_close(gap: int, velocity: float) -> int:
    if gap <= 0:
        return 0
    if velocity <= 0:
        return 999
    return int(math.ceil(gap / velocity))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Scale Velocity Forecast v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- model_gap_weeks_to_close: `{payload.get('model_gap_weeks_to_close')}`",
        f"- mutation_gap_weeks_to_close: `{payload.get('mutation_gap_weeks_to_close')}`",
        f"- on_track_within_horizon: `{payload.get('on_track_within_horizon')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Forecast weekly scale velocity against target gap")
    parser.add_argument("--scale-target-gap-summary", required=True)
    parser.add_argument("--scale-history-summary", required=True)
    parser.add_argument("--default-model-velocity", type=float, default=6.0)
    parser.add_argument("--default-mutation-velocity", type=float, default=200.0)
    parser.add_argument("--out", default="artifacts/dataset_scale_velocity_forecast_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    gap = _load_json(args.scale_target_gap_summary)
    history = _load_json(args.scale_history_summary)
    reasons: list[str] = []
    if not gap:
        reasons.append("scale_target_gap_summary_missing")
    if not history:
        reasons.append("scale_history_summary_missing")

    model_gap = _to_int(gap.get("gap_models", 0))
    mut_gap = _to_int(gap.get("gap_reproducible_mutations", 0))
    target_horizon = max(1, _to_int(gap.get("target_horizon_weeks", 12)))

    model_velocity = float(args.default_model_velocity)
    history_model_delta = _to_int(history.get("delta_canonical_total_models", 0))
    history_avg_growth = _to_float(history.get("avg_canonical_net_growth_models", 0.0))
    if history_model_delta > 0:
        model_velocity = float(history_model_delta)
    elif history_avg_growth > 0:
        model_velocity = float(history_avg_growth)

    mutation_velocity = float(args.default_mutation_velocity)
    history_mut_delta = _to_int(history.get("delta_reproducible_mutations", 0))
    avg_mut = _to_float(history.get("avg_reproducible_mutations", 0.0))
    if history_mut_delta > 0:
        mutation_velocity = float(history_mut_delta)
    elif avg_mut > 0:
        mutation_velocity = max(float(args.default_mutation_velocity), avg_mut * 0.05)

    model_gap_weeks = _weeks_to_close(model_gap, model_velocity)
    mutation_gap_weeks = _weeks_to_close(mut_gap, mutation_velocity)
    on_track = model_gap_weeks <= target_horizon and mutation_gap_weeks <= target_horizon

    alerts: list[str] = []
    if model_gap_weeks > target_horizon:
        alerts.append("model_gap_closure_beyond_horizon")
    if mutation_gap_weeks > target_horizon:
        alerts.append("mutation_gap_closure_beyond_horizon")
    if model_velocity <= 0:
        alerts.append("model_velocity_zero")
    if mutation_velocity <= 0:
        alerts.append("mutation_velocity_zero")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "model_velocity_per_week": round(model_velocity, 4),
        "mutation_velocity_per_week": round(mutation_velocity, 4),
        "model_gap_weeks_to_close": model_gap_weeks,
        "mutation_gap_weeks_to_close": mutation_gap_weeks,
        "on_track_within_horizon": on_track,
        "target_horizon_weeks": target_horizon,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "scale_target_gap_summary": args.scale_target_gap_summary,
            "scale_history_summary": args.scale_history_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "model_gap_weeks_to_close": model_gap_weeks, "mutation_gap_weeks_to_close": mutation_gap_weeks}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
