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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Anchor Brief v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- anchor_brief_score: `{payload.get('anchor_brief_score')}`",
        f"- recommendation: `{payload.get('recommendation')}`",
        f"- confidence_band: `{payload.get('confidence_band')}`",
        "",
        "## Claims",
        "",
    ]
    claims = payload.get("claims") if isinstance(payload.get("claims"), list) else []
    if claims:
        for c in claims:
            lines.append(f"- `{c}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Alerts", ""])
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for a in alerts:
            lines.append(f"- `{a}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build moat anchor brief from moat and governance evidence")
    parser.add_argument("--moat-trend-snapshot-summary", required=True)
    parser.add_argument("--real-model-intake-portfolio-summary", required=True)
    parser.add_argument("--mutation-coverage-depth-summary", required=True)
    parser.add_argument("--failure-distribution-stability-summary", required=True)
    parser.add_argument("--governance-snapshot-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_anchor_brief_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    moat = _load_json(args.moat_trend_snapshot_summary)
    portfolio = _load_json(args.real_model_intake_portfolio_summary)
    coverage = _load_json(args.mutation_coverage_depth_summary)
    stability = _load_json(args.failure_distribution_stability_summary)
    governance = _load_json(args.governance_snapshot_summary)

    reasons: list[str] = []
    if not moat:
        reasons.append("moat_trend_snapshot_summary_missing")
    if not portfolio:
        reasons.append("real_model_intake_portfolio_summary_missing")
    if not coverage:
        reasons.append("mutation_coverage_depth_summary_missing")
    if not stability:
        reasons.append("failure_distribution_stability_summary_missing")

    moat_score = _to_float((moat.get("metrics") or {}).get("moat_score", moat.get("moat_score", 0.0)))
    execution_readiness = _to_float(((moat.get("metrics") or {}).get("execution_readiness_index", 0.0)))
    portfolio_strength = _to_float(portfolio.get("portfolio_strength_score", 0.0))
    total_real_models = _to_int(portfolio.get("total_real_models", 0))
    large_models = _to_int(portfolio.get("large_models", 0))
    coverage_depth_score = _to_float(coverage.get("coverage_depth_score", 0.0))
    high_risk_gaps_count = _to_int(coverage.get("high_risk_gaps_count", 0))
    stability_score = _to_float(stability.get("stability_score", 0.0))
    rare_replay_rate = _to_float(stability.get("rare_failure_replay_rate", 0.0))
    governance_status = str(governance.get("status") or "")

    score = (
        moat_score * 0.28
        + execution_readiness * 0.16
        + portfolio_strength * 0.18
        + coverage_depth_score * 0.18
        + stability_score * 0.2
    )
    if rare_replay_rate >= 0.8:
        score += 3.0
    elif rare_replay_rate < 0.5:
        score -= 5.0
    if high_risk_gaps_count > 0:
        score -= min(10.0, high_risk_gaps_count * 3.0)
    if governance_status == "PASS":
        score += 2.0
    elif governance_status == "NEEDS_REVIEW":
        score -= 2.0
    elif governance_status == "FAIL":
        score -= 8.0
    score = round(_clamp(score), 2)

    alerts: list[str] = []
    if total_real_models < 3:
        alerts.append("real_model_count_low")
    if large_models < 1:
        alerts.append("large_model_count_low")
    if high_risk_gaps_count > 0:
        alerts.append("mutation_high_risk_gaps_present")
    if rare_replay_rate < 0.5:
        alerts.append("rare_failure_replay_rate_low")
    if governance_status == "FAIL":
        alerts.append("governance_snapshot_failed")

    recommendation = "HOLD"
    if score >= 80 and not alerts:
        recommendation = "PUBLISH"
    elif score >= 68:
        recommendation = "PUBLISH_WITH_GUARDS"

    confidence_band = "low"
    if score >= 80:
        confidence_band = "high"
    elif score >= 65:
        confidence_band = "medium"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif recommendation != "PUBLISH":
        status = "NEEDS_REVIEW"

    claims = [
        f"moat_score={moat_score}",
        f"execution_readiness_index={execution_readiness}",
        f"total_real_models={total_real_models}",
        f"large_models={large_models}",
        f"coverage_depth_score={coverage_depth_score}",
        f"stability_score={stability_score}",
        f"rare_failure_replay_rate={rare_replay_rate}",
    ]

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "anchor_brief_score": score,
        "recommendation": recommendation,
        "confidence_band": confidence_band,
        "claims": claims,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "moat_score": moat_score,
            "execution_readiness_index": execution_readiness,
            "portfolio_strength_score": portfolio_strength,
            "total_real_models": total_real_models,
            "large_models": large_models,
            "coverage_depth_score": coverage_depth_score,
            "high_risk_gaps_count": high_risk_gaps_count,
            "stability_score": stability_score,
            "rare_failure_replay_rate": rare_replay_rate,
            "governance_status": governance_status,
        },
        "sources": {
            "moat_trend_snapshot_summary": args.moat_trend_snapshot_summary,
            "real_model_intake_portfolio_summary": args.real_model_intake_portfolio_summary,
            "mutation_coverage_depth_summary": args.mutation_coverage_depth_summary,
            "failure_distribution_stability_summary": args.failure_distribution_stability_summary,
            "governance_snapshot_summary": args.governance_snapshot_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "anchor_brief_score": score, "recommendation": recommendation}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
