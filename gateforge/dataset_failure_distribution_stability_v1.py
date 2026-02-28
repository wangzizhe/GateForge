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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _count_map(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, int):
            out[k] = max(0, v)
        elif isinstance(v, float):
            out[k] = max(0, int(v))
    return out


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole, 4)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Distribution Stability v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- stability_score: `{payload.get('stability_score')}`",
        f"- drift_band: `{payload.get('drift_band')}`",
        f"- rare_failure_replay_rate: `{payload.get('rare_failure_replay_rate')}`",
        f"- distribution_drift_score: `{payload.get('distribution_drift_score')}`",
        f"- delta_distribution_drift_score: `{payload.get('delta_distribution_drift_score')}`",
        f"- delta_regression_rate_after: `{payload.get('delta_regression_rate_after')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate failure distribution stability over time windows")
    parser.add_argument("--current-benchmark-summary", required=True)
    parser.add_argument("--previous-benchmark-summary", required=True)
    parser.add_argument("--rare-prev-count-threshold", type=int, default=1)
    parser.add_argument("--max-drift-score", type=float, default=0.25)
    parser.add_argument("--max-drift-score-increase", type=float, default=0.08)
    parser.add_argument("--max-regression-rate-after", type=float, default=0.15)
    parser.add_argument("--max-regression-rate-increase", type=float, default=0.05)
    parser.add_argument("--min-rare-failure-replay-rate", type=float, default=0.5)
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_stability_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current_benchmark_summary)
    previous = _load_json(args.previous_benchmark_summary)

    reasons: list[str] = []
    if not current:
        reasons.append("current_benchmark_summary_missing")
    if not previous:
        reasons.append("previous_benchmark_summary_missing")

    curr_drift = _to_float(current.get("distribution_drift_score", 0.0))
    prev_drift = _to_float(previous.get("distribution_drift_score", 0.0))
    delta_drift = round(curr_drift - prev_drift, 6)

    curr_reg = _to_float(current.get("regression_rate_after", 0.0))
    prev_reg = _to_float(previous.get("regression_rate_after", 0.0))
    delta_reg = round(curr_reg - prev_reg, 6)

    prev_failure_counts = _count_map(((previous.get("distribution") or {}).get("failure_type_after")))
    curr_failure_counts = _count_map(((current.get("distribution") or {}).get("failure_type_after")))

    rare_threshold = max(0, int(args.rare_prev_count_threshold))
    rare_prev_types = sorted([k for k, v in prev_failure_counts.items() if v <= rare_threshold])
    rare_replayed = sorted([k for k in rare_prev_types if curr_failure_counts.get(k, 0) > 0])
    rare_rate = _ratio(len(rare_replayed), len(rare_prev_types))

    alerts: list[str] = []
    if curr_drift > float(args.max_drift_score):
        alerts.append("distribution_drift_score_high")
    if delta_drift > float(args.max_drift_score_increase):
        alerts.append("distribution_drift_score_increasing")
    if curr_reg > float(args.max_regression_rate_after):
        alerts.append("regression_rate_after_high")
    if delta_reg > float(args.max_regression_rate_increase):
        alerts.append("regression_rate_after_increasing")
    if rare_prev_types and rare_rate < float(args.min_rare_failure_replay_rate):
        alerts.append("rare_failure_replay_rate_low")

    drift_band = "low"
    if curr_drift >= 0.3:
        drift_band = "high"
    elif curr_drift >= 0.18:
        drift_band = "medium"

    stability_score = 84.0
    stability_score -= min(36.0, curr_drift * 100.0)
    stability_score -= min(14.0, max(0.0, delta_drift) * 120.0)
    stability_score -= min(22.0, curr_reg * 100.0)
    stability_score -= min(10.0, max(0.0, delta_reg) * 100.0)
    if rare_prev_types:
        stability_score += min(8.0, rare_rate * 8.0)
    stability_score = round(_clamp(stability_score), 2)

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stability_score": stability_score,
        "drift_band": drift_band,
        "distribution_drift_score": curr_drift,
        "previous_distribution_drift_score": prev_drift,
        "delta_distribution_drift_score": delta_drift,
        "regression_rate_after": curr_reg,
        "previous_regression_rate_after": prev_reg,
        "delta_regression_rate_after": delta_reg,
        "rare_prev_failure_types": rare_prev_types,
        "rare_failure_replayed_types": rare_replayed,
        "rare_failure_replay_rate": rare_rate,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current_benchmark_summary": args.current_benchmark_summary,
            "previous_benchmark_summary": args.previous_benchmark_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "stability_score": stability_score,
                "drift_band": drift_band,
                "rare_failure_replay_rate": rare_rate,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
