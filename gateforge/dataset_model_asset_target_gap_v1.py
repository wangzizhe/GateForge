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


def _gap_points(current: float, target: float, weight: float) -> tuple[float, float]:
    if target <= 0:
        return 0.0, 1.0
    ratio = min(max(current / target, 0.0), 1.0)
    points = (1.0 - ratio) * weight
    return points, ratio


def _severity(points: float) -> str:
    if points >= 20:
        return "high"
    if points >= 8:
        return "medium"
    if points > 0:
        return "low"
    return "none"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Model Asset Target Gap v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- target_gap_score: `{payload.get('target_gap_score')}`",
        f"- critical_gap_count: `{payload.get('critical_gap_count')}`",
        f"- top_action: `{(payload.get('top_actions') or [''])[0]}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute model asset target gaps and next actions")
    parser.add_argument("--real-model-intake-portfolio-summary", required=True)
    parser.add_argument("--model-asset-momentum-summary", required=True)
    parser.add_argument("--mutation-coverage-depth-summary", required=True)
    parser.add_argument("--failure-distribution-stability-summary", required=True)
    parser.add_argument("--target-total-real-models", type=int, default=12)
    parser.add_argument("--target-large-models", type=int, default=4)
    parser.add_argument("--target-mutation-coverage-depth-score", type=float, default=85.0)
    parser.add_argument("--target-failure-distribution-stability-score", type=float, default=80.0)
    parser.add_argument("--target-delta-total-real-models", type=int, default=2)
    parser.add_argument("--target-delta-large-models", type=int, default=1)
    parser.add_argument("--out", default="artifacts/dataset_model_asset_target_gap_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    portfolio = _load_json(args.real_model_intake_portfolio_summary)
    momentum = _load_json(args.model_asset_momentum_summary)
    coverage = _load_json(args.mutation_coverage_depth_summary)
    stability = _load_json(args.failure_distribution_stability_summary)

    reasons: list[str] = []
    if not portfolio:
        reasons.append("real_model_intake_portfolio_summary_missing")
    if not momentum:
        reasons.append("model_asset_momentum_summary_missing")
    if not coverage:
        reasons.append("mutation_coverage_depth_summary_missing")
    if not stability:
        reasons.append("failure_distribution_stability_summary_missing")

    current_total = _to_int(portfolio.get("total_real_models", 0))
    current_large = _to_int(portfolio.get("large_models", 0))
    current_cov = _to_float(portfolio.get("coverage_depth_score", coverage.get("coverage_depth_score", 0.0)))
    current_stability = _to_float(stability.get("stability_score", 0.0))
    current_delta_total = _to_int(momentum.get("delta_total_real_models", 0))
    current_delta_large = _to_int(momentum.get("delta_large_models", 0))

    specs = [
        ("total_real_models", float(current_total), float(args.target_total_real_models), 25.0, "Expand real model intake by priority licenses/domains"),
        ("large_models", float(current_large), float(args.target_large_models), 25.0, "Prioritize large-scale Modelica systems in intake board"),
        ("mutation_coverage_depth_score", current_cov, float(args.target_mutation_coverage_depth_score), 15.0, "Increase high-risk mutation recipes and execution depth"),
        ("failure_distribution_stability_score", current_stability, float(args.target_failure_distribution_stability_score), 15.0, "Stabilize failure distribution via replay and balancing"),
        ("delta_total_real_models", float(current_delta_total), float(args.target_delta_total_real_models), 10.0, "Raise weekly accepted real models throughput"),
        ("delta_large_models", float(current_delta_large), float(args.target_delta_large_models), 10.0, "Ensure at least one new large model per intake cycle"),
    ]

    gap_items: list[dict] = []
    target_gap_score = 0.0
    top_actions: list[str] = []
    critical_gap_count = 0
    for gap_id, current, target, weight, action in specs:
        points, ratio = _gap_points(current, target, weight)
        target_gap_score += points
        sev = _severity(points)
        if sev in {"high", "medium"}:
            top_actions.append(action)
        if sev == "high":
            critical_gap_count += 1
        gap_items.append(
            {
                "gap_id": gap_id,
                "current": round(current, 4),
                "target": round(target, 4),
                "attainment_ratio": round(ratio, 4),
                "gap_points": round(points, 2),
                "severity": sev,
                "recommendation": action,
            }
        )

    target_gap_score = round(target_gap_score, 2)
    if not top_actions:
        top_actions = ["Maintain momentum and keep targets updated each milestone"]

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif critical_gap_count >= 2 or target_gap_score >= 45:
        status = "FAIL"
    elif target_gap_score > 0:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target_gap_score": target_gap_score,
        "critical_gap_count": critical_gap_count,
        "gaps": sorted(gap_items, key=lambda x: float(x.get("gap_points", 0.0)), reverse=True),
        "top_actions": top_actions[:5],
        "reasons": sorted(set(reasons)),
        "metrics": {
            "total_real_models": current_total,
            "large_models": current_large,
            "mutation_coverage_depth_score": current_cov,
            "failure_distribution_stability_score": current_stability,
            "delta_total_real_models": current_delta_total,
            "delta_large_models": current_delta_large,
        },
        "targets": {
            "total_real_models": args.target_total_real_models,
            "large_models": args.target_large_models,
            "mutation_coverage_depth_score": args.target_mutation_coverage_depth_score,
            "failure_distribution_stability_score": args.target_failure_distribution_stability_score,
            "delta_total_real_models": args.target_delta_total_real_models,
            "delta_large_models": args.target_delta_large_models,
        },
        "sources": {
            "real_model_intake_portfolio_summary": args.real_model_intake_portfolio_summary,
            "model_asset_momentum_summary": args.model_asset_momentum_summary,
            "mutation_coverage_depth_summary": args.mutation_coverage_depth_summary,
            "failure_distribution_stability_summary": args.failure_distribution_stability_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "target_gap_score": target_gap_score, "critical_gap_count": critical_gap_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
