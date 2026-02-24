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


def _build_advice(governance_snapshot: dict, mutation_dashboard: dict, medium_dashboard: dict) -> tuple[dict, dict]:
    reasons: list[str] = []
    threshold_patch = {
        "require_min_top_score_margin": None,
        "require_min_explanation_quality": None,
    }

    signals = {
        "governance_status": str(governance_snapshot.get("status") or "UNKNOWN"),
        "governance_risk_count": len(governance_snapshot.get("risks") or []),
        "governance_strict_non_pass_rate": _to_float(
            (governance_snapshot.get("kpis") or {}).get("strict_non_pass_rate")
        ),
        "mutation_bundle_status": str(mutation_dashboard.get("bundle_status") or "UNKNOWN"),
        "mutation_match_rate": _to_float(mutation_dashboard.get("latest_match_rate")),
        "mutation_gate_pass_rate": _to_float(mutation_dashboard.get("latest_gate_pass_rate")),
        "mutation_compare_decision": str(mutation_dashboard.get("compare_decision") or "UNKNOWN"),
        "mutation_trend_status": str(mutation_dashboard.get("trend_status") or "UNKNOWN"),
        "medium_bundle_status": str(medium_dashboard.get("bundle_status") or "UNKNOWN"),
        "medium_pass_rate": _to_float(medium_dashboard.get("pass_rate")),
        "medium_mismatch_case_count": _to_int(medium_dashboard.get("mismatch_case_count")),
        "medium_trend_delta_pass_rate": _to_float(medium_dashboard.get("trend_delta_pass_rate")),
        "medium_advisor_decision": str(medium_dashboard.get("advisor_decision") or "UNKNOWN"),
    }

    score = 0

    if signals["governance_status"] == "FAIL":
        reasons.append("governance_snapshot_fail")
        score += 4
    elif signals["governance_status"] == "NEEDS_REVIEW":
        reasons.append("governance_snapshot_needs_review")
        score += 2

    if signals["governance_strict_non_pass_rate"] >= 0.5:
        reasons.append("strict_non_pass_rate_high")
        score += 2

    if signals["mutation_compare_decision"] == "FAIL":
        reasons.append("mutation_compare_regressed")
        score += 3
    if signals["mutation_trend_status"] == "NEEDS_REVIEW":
        reasons.append("mutation_trend_needs_review")
        score += 2
    if 0.0 < signals["mutation_match_rate"] < 0.98:
        reasons.append("mutation_match_rate_below_target")
        score += 1
        threshold_patch["require_min_top_score_margin"] = 2
    if 0.0 < signals["mutation_gate_pass_rate"] < 0.98:
        reasons.append("mutation_gate_pass_rate_below_target")
        score += 1
        threshold_patch["require_min_explanation_quality"] = 85

    if signals["medium_bundle_status"] == "FAIL":
        reasons.append("medium_dashboard_bundle_fail")
        score += 2
    if signals["medium_advisor_decision"] == "TIGHTEN":
        reasons.append("medium_dashboard_advisor_tighten")
        score += 2
    if signals["medium_mismatch_case_count"] >= 1:
        reasons.append("medium_mismatch_cases_present")
        score += 1
    if signals["medium_trend_delta_pass_rate"] <= -0.05:
        reasons.append("medium_pass_rate_regression")
        score += 1

    if score >= 5:
        suggested_profile = "industrial_strict"
        confidence = 0.84
        threshold_patch["require_min_top_score_margin"] = max(
            int(threshold_patch["require_min_top_score_margin"] or 0), 2
        )
        threshold_patch["require_min_explanation_quality"] = max(
            int(threshold_patch["require_min_explanation_quality"] or 0), 85
        )
    elif score >= 2:
        suggested_profile = "default"
        confidence = 0.7
    else:
        suggested_profile = "default"
        confidence = 0.62

    if not reasons:
        reasons.append("cross_layer_signals_stable")

    advice = {
        "suggested_policy_profile": suggested_profile,
        "confidence": round(confidence, 2),
        "reasons": sorted(set(reasons)),
        "threshold_patch": threshold_patch,
        "dry_run": True,
    }
    return advice, signals


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice", {})
    patch = advice.get("threshold_patch", {})
    lines = [
        "# GateForge Policy Auto-Tune Advisor",
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

    lines.extend(["", "## Signals", ""])
    for k in sorted((payload.get("signals") or {}).keys()):
        lines.append(f"- {k}: `{payload['signals'][k]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-layer policy auto-tuning advisor")
    parser.add_argument(
        "--governance-snapshot",
        default="artifacts/governance_snapshot_demo/summary.json",
        help="governance snapshot summary json",
    )
    parser.add_argument(
        "--mutation-dashboard",
        default="artifacts/mutation_dashboard_demo/summary.json",
        help="mutation dashboard summary json",
    )
    parser.add_argument(
        "--medium-dashboard",
        default="artifacts/benchmark_medium_v1/dashboard.json",
        help="medium benchmark dashboard json",
    )
    parser.add_argument(
        "--out",
        default="artifacts/policy_autotune_demo/advisor.json",
        help="advisor output json",
    )
    parser.add_argument("--report-out", default=None, help="advisor output markdown")
    args = parser.parse_args()

    governance = _load_json(args.governance_snapshot)
    mutation = _load_json(args.mutation_dashboard)
    medium = _load_json(args.medium_dashboard)

    advice, signals = _build_advice(governance, mutation, medium)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "governance_snapshot": args.governance_snapshot,
            "mutation_dashboard": args.mutation_dashboard,
            "medium_dashboard": args.medium_dashboard,
        },
        "advice": advice,
        "signals": signals,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "suggested_policy_profile": advice.get("suggested_policy_profile"),
                "confidence": advice.get("confidence"),
                "reasons_count": len(advice.get("reasons") or []),
            }
        )
    )


if __name__ == "__main__":
    main()
