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
        "# GateForge Model Asset Momentum v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- momentum_score: `{payload.get('momentum_score')}`",
        f"- delta_total_real_models: `{payload.get('delta_total_real_models')}`",
        f"- delta_large_models: `{payload.get('delta_large_models')}`",
        f"- delta_mutation_coverage_depth_score: `{payload.get('delta_mutation_coverage_depth_score')}`",
        f"- delta_stability_score: `{payload.get('delta_stability_score')}`",
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
    parser = argparse.ArgumentParser(description="Compute model-asset momentum from portfolio/coverage/stability deltas")
    parser.add_argument("--current-intake-portfolio", required=True)
    parser.add_argument("--previous-intake-portfolio", required=True)
    parser.add_argument("--current-mutation-coverage-depth", required=True)
    parser.add_argument("--previous-mutation-coverage-depth", required=True)
    parser.add_argument("--current-failure-distribution-stability", required=True)
    parser.add_argument("--previous-failure-distribution-stability", required=True)
    parser.add_argument("--min-momentum-score", type=float, default=72.0)
    parser.add_argument("--out", default="artifacts/dataset_model_asset_momentum_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    cur_portfolio = _load_json(args.current_intake_portfolio)
    prev_portfolio = _load_json(args.previous_intake_portfolio)
    cur_coverage = _load_json(args.current_mutation_coverage_depth)
    prev_coverage = _load_json(args.previous_mutation_coverage_depth)
    cur_stability = _load_json(args.current_failure_distribution_stability)
    prev_stability = _load_json(args.previous_failure_distribution_stability)

    reasons: list[str] = []
    if not cur_portfolio:
        reasons.append("current_intake_portfolio_missing")
    if not prev_portfolio:
        reasons.append("previous_intake_portfolio_missing")
    if not cur_coverage:
        reasons.append("current_mutation_coverage_depth_missing")
    if not prev_coverage:
        reasons.append("previous_mutation_coverage_depth_missing")
    if not cur_stability:
        reasons.append("current_failure_distribution_stability_missing")
    if not prev_stability:
        reasons.append("previous_failure_distribution_stability_missing")

    cur_total = _to_int(cur_portfolio.get("total_real_models", 0))
    prev_total = _to_int(prev_portfolio.get("total_real_models", 0))
    cur_large = _to_int(cur_portfolio.get("large_models", 0))
    prev_large = _to_int(prev_portfolio.get("large_models", 0))

    delta_total = cur_total - prev_total
    delta_large = cur_large - prev_large

    cur_cov = _to_float(cur_coverage.get("coverage_depth_score", 0.0))
    prev_cov = _to_float(prev_coverage.get("coverage_depth_score", 0.0))
    delta_cov = round(cur_cov - prev_cov, 4)

    cur_stab = _to_float(cur_stability.get("stability_score", 0.0))
    prev_stab = _to_float(prev_stability.get("stability_score", 0.0))
    delta_stab = round(cur_stab - prev_stab, 4)

    cur_rare_replay = _to_float(cur_stability.get("rare_failure_replay_rate", 0.0))
    prev_rare_replay = _to_float(prev_stability.get("rare_failure_replay_rate", 0.0))
    delta_rare_replay = round(cur_rare_replay - prev_rare_replay, 4)

    momentum_score = _clamp(
        52.0
        + min(18.0, max(-12.0, delta_total * 6.0))
        + min(15.0, max(-12.0, delta_large * 10.0))
        + min(12.0, max(-10.0, delta_cov * 0.9))
        + min(10.0, max(-8.0, delta_stab * 0.7))
        + min(8.0, max(-6.0, delta_rare_replay * 12.0))
    )
    momentum_score = round(momentum_score, 2)

    alerts: list[str] = []
    if delta_total < 0:
        alerts.append("total_real_models_decreasing")
    if delta_large < 0:
        alerts.append("large_models_decreasing")
    if delta_cov < 0:
        alerts.append("mutation_coverage_depth_score_decreasing")
    if delta_stab < 0:
        alerts.append("failure_distribution_stability_score_decreasing")
    if delta_rare_replay < 0:
        alerts.append("rare_failure_replay_rate_decreasing")
    if momentum_score < float(args.min_momentum_score):
        alerts.append("momentum_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "momentum_score": momentum_score,
        "delta_total_real_models": delta_total,
        "delta_large_models": delta_large,
        "delta_mutation_coverage_depth_score": delta_cov,
        "delta_stability_score": delta_stab,
        "delta_rare_failure_replay_rate": delta_rare_replay,
        "current_total_real_models": cur_total,
        "current_large_models": cur_large,
        "current_mutation_coverage_depth_score": cur_cov,
        "current_stability_score": cur_stab,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current_intake_portfolio": args.current_intake_portfolio,
            "previous_intake_portfolio": args.previous_intake_portfolio,
            "current_mutation_coverage_depth": args.current_mutation_coverage_depth,
            "previous_mutation_coverage_depth": args.previous_mutation_coverage_depth,
            "current_failure_distribution_stability": args.current_failure_distribution_stability,
            "previous_failure_distribution_stability": args.previous_failure_distribution_stability,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "momentum_score": momentum_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
