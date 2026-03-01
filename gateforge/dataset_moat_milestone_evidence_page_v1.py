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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Milestone Evidence Page v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- publishable: `{payload.get('publishable')}`",
        f"- evidence_page_score: `{payload.get('evidence_page_score')}`",
        f"- milestone_decision: `{payload.get('milestone_decision')}`",
        f"- target_gap_pressure_index: `{payload.get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{payload.get('model_asset_target_gap_score')}`",
        f"- target_gap_supply_pressure_index: `{payload.get('target_gap_supply_pressure_index')}`",
        "",
        "## Headline",
        "",
        f"- `{payload.get('headline')}`",
        "",
        "## Risk Disclosures",
        "",
    ]
    risks = payload.get("risk_disclosures") if isinstance(payload.get("risk_disclosures"), list) else []
    if risks:
        for r in risks:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public moat+milestone evidence page")
    parser.add_argument("--moat-trend-snapshot-summary", required=True)
    parser.add_argument("--milestone-checkpoint-summary", required=True)
    parser.add_argument("--milestone-checkpoint-trend-summary", default=None)
    parser.add_argument("--milestone-public-brief-summary", required=True)
    parser.add_argument("--snapshot-moat-alignment-summary", default=None)
    parser.add_argument("--min-publish-score", type=float, default=76.0)
    parser.add_argument("--out", default="artifacts/dataset_moat_milestone_evidence_page_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    moat = _load_json(args.moat_trend_snapshot_summary)
    checkpoint = _load_json(args.milestone_checkpoint_summary)
    checkpoint_trend = _load_json(args.milestone_checkpoint_trend_summary)
    brief = _load_json(args.milestone_public_brief_summary)
    alignment = _load_json(args.snapshot_moat_alignment_summary)

    reasons: list[str] = []
    if not moat:
        reasons.append("moat_trend_snapshot_missing")
    if not checkpoint:
        reasons.append("milestone_checkpoint_summary_missing")
    if not brief:
        reasons.append("milestone_public_brief_summary_missing")

    moat_status = str(moat.get("status") or "")
    moat_score = _to_float((moat.get("metrics") or {}).get("moat_score", 0.0))
    execution_readiness_index = _to_float((moat.get("metrics") or {}).get("execution_readiness_index", 0.0))
    checkpoint_status = str(checkpoint.get("status") or "")
    checkpoint_score = _to_float(checkpoint.get("checkpoint_score", 0.0))
    milestone_decision = str(checkpoint.get("milestone_decision") or "UNKNOWN")
    trend_status = str(checkpoint_trend.get("status") or "")
    trend_transition = str(((checkpoint_trend.get("trend") or {}).get("status_transition")) or "")
    brief_status = str(brief.get("milestone_status") or "")
    target_gap_narrative_status = str(brief.get("target_gap_narrative_status") or "")
    target_gap_pressure = _to_float(brief.get("target_gap_pressure_index", 0.0))
    target_gap_score = _to_float(brief.get("model_asset_target_gap_score", 0.0))
    target_gap_supply_pressure = _to_float(brief.get("target_gap_supply_pressure_index", 0.0))
    alignment_score = _to_float(alignment.get("alignment_score", 75.0))

    score = moat_score * 0.33 + checkpoint_score * 0.33 + execution_readiness_index * 0.18 + alignment_score * 0.1
    if brief_status == "PASS":
        score += 6.0
    elif brief_status == "NEEDS_REVIEW":
        score -= 4.0
    elif brief_status == "FAIL":
        score -= 10.0

    if trend_status == "PASS":
        score += 3.0
    elif trend_status == "NEEDS_REVIEW":
        score -= 3.0
    elif trend_status == "FAIL":
        score -= 8.0

    score += min(6.0, target_gap_pressure * 0.06)
    score -= min(8.0, target_gap_score * 0.16)
    score -= min(6.0, target_gap_supply_pressure * 0.08)
    if target_gap_narrative_status == "PASS":
        score += 2.0
    elif target_gap_narrative_status == "NEEDS_REVIEW":
        score -= 2.0
    elif target_gap_narrative_status == "FAIL":
        score -= 6.0

    if trend_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        score -= 4.0

    if milestone_decision == "GO":
        score += 3.0
    elif milestone_decision == "LIMITED_GO":
        score -= 2.0
    elif milestone_decision == "HOLD":
        score -= 10.0

    score = _round(_clamp(score))

    risk_disclosures: list[str] = []
    if moat_status in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("moat_status_not_pass")
    if checkpoint_status in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("milestone_checkpoint_not_pass")
    if brief_status in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("milestone_brief_not_pass")
    if milestone_decision != "GO":
        risk_disclosures.append("milestone_decision_not_go")
    if trend_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        risk_disclosures.append("milestone_trend_worsened")
    if target_gap_pressure and target_gap_pressure < 60.0:
        risk_disclosures.append("target_gap_pressure_low")
    if target_gap_score >= 30.0:
        risk_disclosures.append("model_asset_target_gap_high")
    if target_gap_supply_pressure >= 65.0:
        risk_disclosures.append("target_gap_supply_pressure_high")
    if target_gap_narrative_status in {"NEEDS_REVIEW", "FAIL"}:
        risk_disclosures.append("target_gap_narrative_not_pass")

    publishable = score >= float(args.min_publish_score) and not reasons and not risk_disclosures

    status = "PASS" if publishable else "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"

    headline = (
        f"GateForge milestone {milestone_decision} with moat score {moat_score} "
        f"and checkpoint score {checkpoint_score}; execution readiness {execution_readiness_index}"
    )

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "publishable": publishable,
        "evidence_page_score": score,
        "headline": headline,
        "milestone_decision": milestone_decision,
        "milestone_status": checkpoint_status,
        "moat_status": moat_status,
        "target_gap_pressure_index": target_gap_pressure,
        "model_asset_target_gap_score": target_gap_score,
        "target_gap_supply_pressure_index": target_gap_supply_pressure,
        "target_gap_narrative_status": target_gap_narrative_status,
        "risk_disclosures": risk_disclosures,
        "public_claims": [
            {
                "claim_id": "claim.moat_score",
                "text": f"Moat score at {moat_score}",
                "value": moat_score,
            },
            {
                "claim_id": "claim.checkpoint_score",
                "text": f"Milestone checkpoint score at {checkpoint_score}",
                "value": checkpoint_score,
            },
            {
                "claim_id": "claim.execution_readiness_index",
                "text": f"Execution readiness index at {execution_readiness_index}",
                "value": execution_readiness_index,
            },
            {
                "claim_id": "claim.milestone_decision",
                "text": f"Milestone decision is {milestone_decision}",
                "value": milestone_decision,
            },
            {
                "claim_id": "claim.target_gap_pressure_index",
                "text": f"Target-gap pressure index at {target_gap_pressure}",
                "value": target_gap_pressure,
            },
            {
                "claim_id": "claim.model_asset_target_gap_score",
                "text": f"Model-asset target-gap score at {target_gap_score}",
                "value": target_gap_score,
            },
        ],
        "sources": {
            "moat_trend_snapshot_summary": args.moat_trend_snapshot_summary,
            "milestone_checkpoint_summary": args.milestone_checkpoint_summary,
            "milestone_checkpoint_trend_summary": args.milestone_checkpoint_trend_summary,
            "milestone_public_brief_summary": args.milestone_public_brief_summary,
            "snapshot_moat_alignment_summary": args.snapshot_moat_alignment_summary,
        },
        "reasons": sorted(set(reasons)),
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "publishable": payload.get("publishable"), "evidence_page_score": score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
