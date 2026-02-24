from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def _advise(dashboard: dict) -> dict:
    latest_decision = str(dashboard.get("latest_effectiveness_decision") or "UNKNOWN")
    trend_status = str(dashboard.get("trend_status") or "UNKNOWN")
    improvement_rate = _to_float(dashboard.get("improvement_rate"))
    regression_rate = _to_float(dashboard.get("regression_rate"))
    trend_alerts_count = int(dashboard.get("trend_alerts_count", 0) or 0)

    reasons: list[str] = []
    threshold_patch = {
        "require_min_top_score_margin": None,
        "require_min_explanation_quality": None,
    }

    action = "KEEP"
    suggested_profile = "default"
    confidence = 0.62

    if latest_decision == "REGRESSED":
        reasons.append("latest_effectiveness_regressed")
        action = "TIGHTEN"
        suggested_profile = "industrial_strict"
        confidence = 0.84
    elif latest_decision == "IMPROVED":
        reasons.append("latest_effectiveness_improved")
        action = "KEEP"
        suggested_profile = "default"
        confidence = 0.74
    else:
        reasons.append("latest_effectiveness_unchanged")

    if trend_status == "NEEDS_REVIEW":
        reasons.append("governance_trend_needs_review")
        action = "TIGHTEN"
        suggested_profile = "industrial_strict"
        confidence = max(confidence, 0.78)

    if regression_rate >= 0.3:
        reasons.append("regression_rate_high")
        action = "TIGHTEN"
        suggested_profile = "industrial_strict"
        confidence = max(confidence, 0.82)
        threshold_patch["require_min_top_score_margin"] = 2
        threshold_patch["require_min_explanation_quality"] = 85

    if regression_rate >= 0.5:
        reasons.append("regression_rate_critical")
        action = "ROLLBACK_REVIEW"
        suggested_profile = "industrial_strict"
        confidence = max(confidence, 0.9)
        threshold_patch["require_min_top_score_margin"] = 3
        threshold_patch["require_min_explanation_quality"] = 90

    if trend_alerts_count >= 2:
        reasons.append("trend_alerts_multiple")
        if threshold_patch["require_min_top_score_margin"] is None:
            threshold_patch["require_min_top_score_margin"] = 2
        if threshold_patch["require_min_explanation_quality"] is None:
            threshold_patch["require_min_explanation_quality"] = 85

    if improvement_rate >= 0.7 and regression_rate == 0.0 and latest_decision == "IMPROVED":
        reasons.append("improvement_rate_strong")
        action = "KEEP"
        suggested_profile = "default"
        confidence = max(confidence, 0.8)
        threshold_patch["require_min_top_score_margin"] = None
        threshold_patch["require_min_explanation_quality"] = None

    return {
        "action": action,
        "suggested_policy_profile": suggested_profile,
        "confidence": round(confidence, 2),
        "reasons": sorted(set(reasons)),
        "threshold_patch": threshold_patch,
        "dry_run": True,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice", {})
    patch = advice.get("threshold_patch", {})
    lines = [
        "# GateForge Policy Auto-Tune Governance Advisor",
        "",
        f"- action: `{advice.get('action')}`",
        f"- suggested_policy_profile: `{advice.get('suggested_policy_profile')}`",
        f"- confidence: `{advice.get('confidence')}`",
        f"- require_min_top_score_margin_patch: `{patch.get('require_min_top_score_margin')}`",
        f"- require_min_explanation_quality_patch: `{patch.get('require_min_explanation_quality')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for r in reasons:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend governance policy action from autotune governance dashboard")
    parser.add_argument(
        "--dashboard",
        default="artifacts/policy_autotune_governance_history_demo/dashboard.json",
        help="autotune governance dashboard summary",
    )
    parser.add_argument(
        "--out",
        default="artifacts/policy_autotune_governance_advisor/summary.json",
        help="advisor output json",
    )
    parser.add_argument("--report-out", default=None, help="advisor output markdown")
    args = parser.parse_args()

    dashboard = _load_json(args.dashboard)
    payload = {
        "dashboard_path": args.dashboard,
        "advice": _advise(dashboard),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "action": payload["advice"].get("action"),
                "suggested_policy_profile": payload["advice"].get("suggested_policy_profile"),
            }
        )
    )


if __name__ == "__main__":
    main()
