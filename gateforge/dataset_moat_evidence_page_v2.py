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
        "# GateForge Moat Evidence Page v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- publishable: `{payload.get('publishable')}`",
        f"- evidence_score: `{payload.get('evidence_score')}`",
        f"- headline: `{payload.get('headline')}`",
        "",
        "## Risk Disclosures",
        "",
    ]
    risks = payload.get("risk_disclosures") if isinstance(payload.get("risk_disclosures"), list) else []
    if risks:
        for risk in risks:
            lines.append(f"- `{risk}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public moat evidence page from anchor + supply + mutation + stability chains")
    parser.add_argument("--moat-anchor-brief-summary", required=True)
    parser.add_argument("--real-model-growth-trend-summary", required=True)
    parser.add_argument("--real-model-supply-pipeline-summary", required=True)
    parser.add_argument("--mutation-coverage-matrix-summary", required=True)
    parser.add_argument("--failure-distribution-stability-history-summary", required=True)
    parser.add_argument("--failure-distribution-stability-history-trend-summary", required=True)
    parser.add_argument("--min-publish-score", type=float, default=78.0)
    parser.add_argument("--out", default="artifacts/dataset_moat_evidence_page_v2/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    anchor = _load_json(args.moat_anchor_brief_summary)
    growth = _load_json(args.real_model_growth_trend_summary)
    supply = _load_json(args.real_model_supply_pipeline_summary)
    matrix = _load_json(args.mutation_coverage_matrix_summary)
    stability_history = _load_json(args.failure_distribution_stability_history_summary)
    stability_history_trend = _load_json(args.failure_distribution_stability_history_trend_summary)

    reasons: list[str] = []
    if not anchor:
        reasons.append("moat_anchor_brief_summary_missing")
    if not growth:
        reasons.append("real_model_growth_trend_summary_missing")
    if not supply:
        reasons.append("real_model_supply_pipeline_summary_missing")
    if not matrix:
        reasons.append("mutation_coverage_matrix_summary_missing")
    if not stability_history:
        reasons.append("failure_distribution_stability_history_summary_missing")
    if not stability_history_trend:
        reasons.append("failure_distribution_stability_history_trend_summary_missing")

    anchor_score = _to_float(anchor.get("anchor_brief_score", 0.0))
    growth_score = _to_float(growth.get("growth_velocity_score", 0.0))
    supply_score = _to_float(supply.get("supply_pipeline_score", 0.0))
    matrix_score = _to_float(matrix.get("matrix_coverage_score", 0.0))
    stability_score = _to_float(stability_history.get("avg_stability_score", 0.0))
    new_models_30d = _to_int(supply.get("new_models_30d", 0))
    large_candidates_30d = _to_int(supply.get("large_model_candidates_30d", 0))

    score = (
        anchor_score * 0.28
        + growth_score * 0.16
        + supply_score * 0.2
        + matrix_score * 0.2
        + stability_score * 0.16
    )
    if new_models_30d >= 2:
        score += 2.0
    if large_candidates_30d >= 1:
        score += 2.0
    score = round(_clamp(score), 2)

    risk_disclosures: list[str] = []
    if str(anchor.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("anchor_brief_not_pass")
    if str(growth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("growth_trend_not_pass")
    if str(supply.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("supply_pipeline_not_pass")
    if str(matrix.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("mutation_matrix_not_pass")
    if str(stability_history.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("stability_history_not_pass")
    if str(stability_history_trend.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("stability_history_trend_not_pass")

    publishable = score >= float(args.min_publish_score) and not reasons and not risk_disclosures
    status = "PASS" if publishable else "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"

    headline = (
        f"Moat evidence score {score} with {new_models_30d} new real models/30d, "
        f"{large_candidates_30d} large candidates, and mutation matrix score {matrix_score}"
    )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "publishable": publishable,
        "evidence_score": score,
        "headline": headline,
        "risk_disclosures": risk_disclosures,
        "public_claims": [
            {"claim_id": "claim.anchor_brief_score", "value": anchor_score},
            {"claim_id": "claim.growth_velocity_score", "value": growth_score},
            {"claim_id": "claim.supply_pipeline_score", "value": supply_score},
            {"claim_id": "claim.matrix_coverage_score", "value": matrix_score},
            {"claim_id": "claim.avg_stability_score", "value": stability_score},
            {"claim_id": "claim.new_models_30d", "value": new_models_30d},
            {"claim_id": "claim.large_model_candidates_30d", "value": large_candidates_30d},
        ],
        "sources": {
            "moat_anchor_brief_summary": args.moat_anchor_brief_summary,
            "real_model_growth_trend_summary": args.real_model_growth_trend_summary,
            "real_model_supply_pipeline_summary": args.real_model_supply_pipeline_summary,
            "mutation_coverage_matrix_summary": args.mutation_coverage_matrix_summary,
            "failure_distribution_stability_history_summary": args.failure_distribution_stability_history_summary,
            "failure_distribution_stability_history_trend_summary": args.failure_distribution_stability_history_trend_summary,
        },
        "reasons": sorted(set(reasons)),
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "publishable": publishable, "evidence_score": score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
