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
        "# GateForge Real Model Growth Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- growth_velocity_score: `{payload.get('growth_velocity_score')}`",
        f"- delta_total_real_models: `{payload.get('delta_total_real_models')}`",
        f"- delta_large_models: `{payload.get('delta_large_models')}`",
        f"- delta_active_domains: `{payload.get('delta_active_domains')}`",
        f"- trend_band: `{payload.get('trend_band')}`",
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
    parser = argparse.ArgumentParser(description="Compare two real model intake portfolios and emit growth trend")
    parser.add_argument("--current-portfolio-summary", required=True)
    parser.add_argument("--previous-portfolio-summary", required=True)
    parser.add_argument("--min-delta-total-models", type=int, default=1)
    parser.add_argument("--min-delta-large-models", type=int, default=0)
    parser.add_argument("--min-delta-active-domains", type=int, default=0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_growth_trend_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current_portfolio_summary)
    previous = _load_json(args.previous_portfolio_summary)

    reasons: list[str] = []
    if not current:
        reasons.append("current_portfolio_summary_missing")
    if not previous:
        reasons.append("previous_portfolio_summary_missing")

    current_total = _to_int(current.get("total_real_models", 0))
    previous_total = _to_int(previous.get("total_real_models", 0))
    current_large = _to_int(current.get("large_models", 0))
    previous_large = _to_int(previous.get("large_models", 0))
    current_domains = _to_int(current.get("active_domains_count", 0))
    previous_domains = _to_int(previous.get("active_domains_count", 0))
    current_strength = _to_float(current.get("portfolio_strength_score", 0.0))
    previous_strength = _to_float(previous.get("portfolio_strength_score", 0.0))

    delta_total = current_total - previous_total
    delta_large = current_large - previous_large
    delta_domains = current_domains - previous_domains
    delta_strength = round(current_strength - previous_strength, 4)

    growth_velocity_score = 50.0
    growth_velocity_score += min(24.0, max(-24.0, delta_total * 6.0))
    growth_velocity_score += min(14.0, max(-14.0, delta_large * 10.0))
    growth_velocity_score += min(10.0, max(-10.0, delta_domains * 4.0))
    growth_velocity_score += min(12.0, max(-12.0, delta_strength * 0.6))
    growth_velocity_score = round(max(0.0, min(100.0, growth_velocity_score)), 2)

    alerts: list[str] = []
    if delta_total < int(args.min_delta_total_models):
        alerts.append("delta_total_real_models_below_target")
    if delta_large < int(args.min_delta_large_models):
        alerts.append("delta_large_models_below_target")
    if delta_domains < int(args.min_delta_active_domains):
        alerts.append("delta_active_domains_below_target")
    if delta_total < 0:
        alerts.append("real_model_total_decreased")
    if delta_large < 0:
        alerts.append("large_model_count_decreased")

    trend_band = "flat"
    if growth_velocity_score >= 75:
        trend_band = "accelerating"
    elif growth_velocity_score >= 60:
        trend_band = "growing"
    elif growth_velocity_score < 45:
        trend_band = "regressing"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "growth_velocity_score": growth_velocity_score,
        "trend_band": trend_band,
        "delta_total_real_models": delta_total,
        "delta_large_models": delta_large,
        "delta_active_domains": delta_domains,
        "delta_portfolio_strength_score": delta_strength,
        "current_total_real_models": current_total,
        "current_large_models": current_large,
        "current_active_domains": current_domains,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current_portfolio_summary": args.current_portfolio_summary,
            "previous_portfolio_summary": args.previous_portfolio_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "growth_velocity_score": growth_velocity_score, "trend_band": trend_band}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
