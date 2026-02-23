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


def _advise(snapshot: dict, trend: dict) -> dict:
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
        "require_min_explanation_quality": None,
    }

    if risk_score >= 60 or "replay_risk_level_high" in risks:
        suggested_profile = "industrial_strict"
        confidence = 0.82
        reasons.append("high_replay_risk_score")
    if latest_mismatch >= 2:
        reasons.append("latest_mismatch_count_high")
        threshold_patch["require_min_top_score_margin"] = 2
    if mismatch_total_delta > 0:
        reasons.append("mismatch_volume_increasing")
        threshold_patch["require_min_explanation_quality"] = 85
    if risk_delta > 0:
        reasons.append("risk_score_increasing")

    if not reasons:
        reasons.append("stable_replay_signals")
        confidence = 0.6

    if suggested_profile == "default" and (threshold_patch["require_min_top_score_margin"] or threshold_patch["require_min_explanation_quality"]):
        confidence = max(confidence, 0.66)

    return {
        "suggested_policy_profile": suggested_profile,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "threshold_patch": threshold_patch,
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
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate policy adjustment advice from replay governance signals")
    parser.add_argument("--snapshot", required=True, help="Replay governance snapshot JSON")
    parser.add_argument("--trend", required=True, help="Replay governance trend JSON")
    parser.add_argument("--out", default="artifacts/governance_policy_advisor/summary.json", help="Output JSON path")
    parser.add_argument("--report", default=None, help="Output markdown path")
    args = parser.parse_args()

    snapshot = _load_json(args.snapshot)
    trend = _load_json(args.trend)
    advice = _advise(snapshot, trend)
    summary = {
        "snapshot_path": args.snapshot,
        "trend_path": args.trend,
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
