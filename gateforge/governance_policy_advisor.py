from __future__ import annotations

import argparse
import json
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _build_why_now(reasons: list[str], evidence_sources: list[dict]) -> dict:
    top_signals = []
    for row in evidence_sources[:5]:
        if isinstance(row, dict):
            top_signals.append({"source": row.get("source"), "value": row.get("value")})
    if not reasons:
        summary = "No active governance pressure signals."
        urgency = "low"
    elif any(r.startswith("apply_status_fail") or r.startswith("high_replay_risk_score") for r in reasons):
        summary = "High-risk governance signals detected; policy tightening is time-sensitive."
        urgency = "high"
    elif any("regressed" in r or "low" in r for r in reasons):
        summary = "Quality and comparability signals are weakening; tighten policy before drift accumulates."
        urgency = "medium"
    else:
        summary = "Early warning signals detected; policy adjustment is recommended."
        urgency = "medium"
    return {
        "summary": summary,
        "urgency": urgency,
        "reason_codes": reasons,
        "top_signals": top_signals,
    }


def _build_scorecard(
    reasons: list[str],
    threshold_patch: dict,
    confidence: float,
    suggested_profile: str,
) -> dict:
    patch_count = sum(1 for _, v in threshold_patch.items() if isinstance(v, int))
    impact = "low"
    if suggested_profile == "industrial_strict" or patch_count >= 2:
        impact = "high"
    elif patch_count == 1:
        impact = "medium"
    execution_risk = "low"
    if patch_count >= 2:
        execution_risk = "medium"
    if any(r.startswith("apply_status_fail") for r in reasons):
        execution_risk = "high"
    priority = "normal"
    if impact == "high" and confidence >= 0.8:
        priority = "urgent"
    elif impact in {"medium", "high"}:
        priority = "high"
    return {
        "impact": impact,
        "execution_risk": execution_risk,
        "confidence": round(confidence, 2),
        "priority": priority,
    }


def _advise(
    snapshot: dict,
    trend: dict,
    compare_summary: dict | None = None,
    apply_summary: dict | None = None,
    mutation_summary: dict | None = None,
) -> dict:
    kpis = snapshot.get("kpis", {}) if isinstance(snapshot.get("kpis"), dict) else {}
    trend_kpi = trend.get("trend", {}).get("kpi_delta", {}) if isinstance(trend.get("trend"), dict) else {}
    risks = set(r for r in (snapshot.get("risks") or []) if isinstance(r, str))

    risk_score = _to_float(kpis.get("risk_score"))
    latest_mismatch = _to_float(kpis.get("latest_mismatch_count"))
    mismatch_total_delta = _to_float(trend_kpi.get("history_mismatch_total_delta"))
    risk_delta = _to_float(trend_kpi.get("risk_score_delta"))

    suggested_profile = "default"
    confidence = 0.55
    reasons: list[str] = []
    threshold_patch = {
        "require_min_top_score_margin": None,
        "require_min_pairwise_net_margin": None,
        "require_min_explanation_quality": None,
    }
    evidence_sources: list[dict] = []

    if risk_score >= 60 or "replay_risk_level_high" in risks:
        suggested_profile = "industrial_strict"
        confidence = 0.82
        reasons.append("high_replay_risk_score")
        evidence_sources.append({"source": "snapshot.kpis.risk_score", "value": risk_score})
    if latest_mismatch >= 2:
        reasons.append("latest_mismatch_count_high")
        threshold_patch["require_min_top_score_margin"] = 2
        evidence_sources.append({"source": "snapshot.kpis.latest_mismatch_count", "value": latest_mismatch})
    if mismatch_total_delta > 0:
        reasons.append("mismatch_volume_increasing")
        threshold_patch["require_min_explanation_quality"] = 85
        evidence_sources.append({"source": "trend.kpi_delta.history_mismatch_total_delta", "value": mismatch_total_delta})
    if risk_delta > 0:
        reasons.append("risk_score_increasing")
        evidence_sources.append({"source": "trend.kpi_delta.risk_score_delta", "value": risk_delta})

    if isinstance(compare_summary, dict) and compare_summary:
        top_margin = compare_summary.get("top_score_margin")
        if isinstance(top_margin, int) and top_margin <= 1:
            reasons.append("compare_top_score_margin_low")
            threshold_patch["require_min_top_score_margin"] = max(
                int(threshold_patch["require_min_top_score_margin"] or 0),
                2,
            )
            evidence_sources.append({"source": "compare.top_score_margin", "value": top_margin})
        completeness = compare_summary.get("explanation_completeness")
        if isinstance(completeness, int) and completeness < 90:
            reasons.append("compare_explanation_completeness_low")
            threshold_patch["require_min_explanation_quality"] = max(
                int(threshold_patch["require_min_explanation_quality"] or 0),
                85,
            )
            evidence_sources.append({"source": "compare.explanation_completeness", "value": completeness})
        leaderboard = compare_summary.get("decision_explanation_leaderboard")
        pairwise_net_margin = None
        if isinstance(leaderboard, list) and leaderboard and isinstance(leaderboard[0], dict):
            pairwise_net_margin = leaderboard[0].get("pairwise_net_margin")
        if isinstance(pairwise_net_margin, int) and pairwise_net_margin <= 1:
            reasons.append("compare_pairwise_net_margin_low")
            threshold_patch["require_min_pairwise_net_margin"] = max(
                int(threshold_patch["require_min_pairwise_net_margin"] or 0),
                2,
            )
            evidence_sources.append({"source": "compare.decision_explanation_leaderboard[0].pairwise_net_margin", "value": pairwise_net_margin})

    if isinstance(apply_summary, dict) and apply_summary:
        apply_status = str(apply_summary.get("final_status") or "").upper()
        if apply_status in {"NEEDS_REVIEW", "FAIL"}:
            reasons.append(f"apply_status_{apply_status.lower()}")
            suggested_profile = "industrial_strict"
            confidence = max(confidence, 0.78)
            evidence_sources.append({"source": "apply.final_status", "value": apply_status})

    if isinstance(mutation_summary, dict) and mutation_summary:
        mutation_trend = str(mutation_summary.get("trend_status") or "")
        mutation_compare = str(mutation_summary.get("compare_decision") or "")
        mutation_match_rate = _to_float(mutation_summary.get("latest_match_rate"))
        mutation_gate_pass_rate = _to_float(mutation_summary.get("latest_gate_pass_rate"))
        if mutation_trend == "NEEDS_REVIEW":
            reasons.append("mutation_trend_needs_review")
            suggested_profile = "industrial_strict"
            confidence = max(confidence, 0.76)
            evidence_sources.append({"source": "mutation.trend_status", "value": mutation_trend})
        if mutation_compare == "FAIL":
            reasons.append("mutation_compare_regressed")
            suggested_profile = "industrial_strict"
            confidence = max(confidence, 0.8)
            evidence_sources.append({"source": "mutation.compare_decision", "value": mutation_compare})
        if 0.0 < mutation_match_rate < 0.98:
            reasons.append("mutation_match_rate_below_target")
            threshold_patch["require_min_top_score_margin"] = max(
                int(threshold_patch["require_min_top_score_margin"] or 0),
                2,
            )
            evidence_sources.append({"source": "mutation.latest_match_rate", "value": mutation_match_rate})
        if 0.0 < mutation_gate_pass_rate < 0.98:
            reasons.append("mutation_gate_pass_rate_below_target")
            threshold_patch["require_min_explanation_quality"] = max(
                int(threshold_patch["require_min_explanation_quality"] or 0),
                85,
            )
            evidence_sources.append({"source": "mutation.latest_gate_pass_rate", "value": mutation_gate_pass_rate})

    if not reasons:
        reasons.append("stable_replay_signals")
        confidence = 0.6

    if suggested_profile == "default" and (
        threshold_patch["require_min_top_score_margin"]
        or threshold_patch["require_min_pairwise_net_margin"]
        or threshold_patch["require_min_explanation_quality"]
    ):
        confidence = max(confidence, 0.66)

    why_now = _build_why_now(reasons, evidence_sources)
    scorecard = _build_scorecard(reasons, threshold_patch, confidence, suggested_profile)
    return {
        "suggested_policy_profile": suggested_profile,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "threshold_patch": threshold_patch,
        "evidence_sources": evidence_sources,
        "why_now": why_now,
        "recommendation_scorecard": scorecard,
        "dry_run": True,
    }


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = summary.get("advice", {})
    patch = advice.get("threshold_patch", {})
    lines = [
        "# GateForge Governance Policy Advisor",
        "",
        f"- suggested_policy_profile: `{advice.get('suggested_policy_profile')}`",
        f"- confidence: `{advice.get('confidence')}`",
        f"- dry_run: `{advice.get('dry_run')}`",
        f"- require_min_top_score_margin_patch: `{patch.get('require_min_top_score_margin')}`",
        f"- require_min_pairwise_net_margin_patch: `{patch.get('require_min_pairwise_net_margin')}`",
        f"- require_min_explanation_quality_patch: `{patch.get('require_min_explanation_quality')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons", [])
    if reasons:
        for r in reasons:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Evidence Sources", ""])
    evidence = advice.get("evidence_sources", [])
    if isinstance(evidence, list) and evidence:
        for row in evidence:
            if isinstance(row, dict):
                lines.append(f"- `{row.get('source')}` = `{row.get('value')}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Why Now", ""])
    why_now = advice.get("why_now", {})
    lines.append(f"- urgency: `{why_now.get('urgency')}`")
    lines.append(f"- summary: `{why_now.get('summary')}`")
    lines.extend(["", "## Recommendation Scorecard", ""])
    scorecard = advice.get("recommendation_scorecard", {})
    lines.append(f"- impact: `{scorecard.get('impact')}`")
    lines.append(f"- execution_risk: `{scorecard.get('execution_risk')}`")
    lines.append(f"- confidence: `{scorecard.get('confidence')}`")
    lines.append(f"- priority: `{scorecard.get('priority')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate policy adjustment advice from replay governance signals")
    parser.add_argument("--snapshot", required=True, help="Replay governance snapshot JSON")
    parser.add_argument("--trend", required=True, help="Replay governance trend JSON")
    parser.add_argument("--compare-summary", default=None, help="Optional governance promote-compare summary JSON")
    parser.add_argument("--apply-summary", default=None, help="Optional governance promote-apply summary JSON")
    parser.add_argument("--mutation-summary", default=None, help="Optional mutation dashboard summary JSON")
    parser.add_argument("--out", default="artifacts/governance_policy_advisor/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    snapshot = _load_json(args.snapshot)
    trend = _load_json(args.trend)
    compare_summary = _load_json(args.compare_summary) if args.compare_summary else None
    apply_summary = _load_json(args.apply_summary) if args.apply_summary else None
    mutation_summary = _load_json(args.mutation_summary) if args.mutation_summary else None
    advice = _advise(
        snapshot,
        trend,
        compare_summary=compare_summary,
        apply_summary=apply_summary,
        mutation_summary=mutation_summary,
    )
    summary = {
        "snapshot_path": args.snapshot,
        "trend_path": args.trend,
        "compare_summary_path": args.compare_summary,
        "apply_summary_path": args.apply_summary,
        "mutation_summary_path": args.mutation_summary,
        "advice": advice,
    }
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "suggested_policy_profile": advice.get("suggested_policy_profile"),
                "confidence": advice.get("confidence"),
            }
        )
    )


if __name__ == "__main__":
    main()
