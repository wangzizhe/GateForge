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


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = summary.get("advice", {})
    patch = advice.get("threshold_patch", {})
    lines = [
        "# GateForge Mutation Policy Advisor",
        "",
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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _advise(dashboard: dict) -> dict:
    match_rate = _to_float(dashboard.get("latest_match_rate"))
    gate_pass_rate = _to_float(dashboard.get("latest_gate_pass_rate"))
    trend_status = str(dashboard.get("trend_status") or "")
    compare_decision = str(dashboard.get("compare_decision") or "")

    reasons: list[str] = []
    suggested = "default"
    confidence = 0.62
    patch = {
        "require_min_top_score_margin": None,
        "require_min_explanation_quality": None,
    }

    if match_rate < 0.98:
        reasons.append("mutation_match_rate_below_target")
        patch["require_min_top_score_margin"] = 2
    if gate_pass_rate < 0.98:
        reasons.append("mutation_gate_pass_rate_below_target")
        patch["require_min_explanation_quality"] = 85
    if trend_status == "NEEDS_REVIEW":
        reasons.append("mutation_trend_needs_review")
        suggested = "industrial_strict"
        confidence = max(confidence, 0.78)
    if compare_decision == "FAIL":
        reasons.append("mutation_pack_compare_regressed")
        suggested = "industrial_strict"
        confidence = max(confidence, 0.82)
        patch["require_min_top_score_margin"] = max(int(patch["require_min_top_score_margin"] or 0), 2)
        patch["require_min_explanation_quality"] = max(int(patch["require_min_explanation_quality"] or 0), 85)

    if not reasons:
        reasons.append("mutation_signals_stable")

    return {
        "suggested_policy_profile": suggested,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "threshold_patch": patch,
        "dry_run": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate policy advice from mutation dashboard signals")
    parser.add_argument("--dashboard", required=True, help="Mutation dashboard summary JSON")
    parser.add_argument("--out", default="artifacts/mutation_policy_advisor/summary.json", help="Advisor JSON path")
    parser.add_argument("--report-out", default=None, help="Advisor markdown path")
    args = parser.parse_args()

    dashboard = _load_json(args.dashboard)
    summary = {
        "dashboard_path": args.dashboard,
        "advice": _advise(dashboard),
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "suggested_policy_profile": summary["advice"].get("suggested_policy_profile"),
                "confidence": summary["advice"].get("confidence"),
            }
        )
    )


if __name__ == "__main__":
    main()
