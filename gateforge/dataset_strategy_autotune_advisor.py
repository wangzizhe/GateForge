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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice", {})
    lines = [
        "# GateForge Dataset Strategy Auto-Tune Advisor",
        "",
        f"- suggested_policy_profile: `{advice.get('suggested_policy_profile')}`",
        f"- suggested_action: `{advice.get('suggested_action')}`",
        f"- confidence: `{advice.get('confidence')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for reason in reasons:
            lines.append(f"- `{reason}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Signals", ""])
    signals = payload.get("signals", {})
    if isinstance(signals, dict):
        for key in sorted(signals):
            lines.append(f"- {key}: `{signals[key]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _build_advice(dataset_governance: dict, dataset_governance_trend: dict, effectiveness: dict) -> tuple[dict, dict]:
    trend_obj = (
        dataset_governance_trend.get("trend")
        if isinstance(dataset_governance_trend.get("trend"), dict)
        else {}
    )
    trend_alerts = trend_obj.get("alerts") if isinstance(trend_obj.get("alerts"), list) else []
    status_counts = dataset_governance.get("status_counts") if isinstance(dataset_governance.get("status_counts"), dict) else {}
    total_records = _to_int(dataset_governance.get("total_records", 0))
    fail_count = _to_int(status_counts.get("FAIL", 0))
    needs_review_count = _to_int(status_counts.get("NEEDS_REVIEW", 0))
    fail_rate = round((fail_count / total_records), 4) if total_records > 0 else 0.0
    needs_review_rate = round((needs_review_count / total_records), 4) if total_records > 0 else 0.0
    effectiveness_decision = str(effectiveness.get("decision") or "UNKNOWN")

    signals = {
        "dataset_governance_latest_status": str(dataset_governance.get("latest_status") or "UNKNOWN"),
        "dataset_governance_fail_rate": fail_rate,
        "dataset_governance_needs_review_rate": needs_review_rate,
        "dataset_governance_trend_status": str(dataset_governance_trend.get("status") or "UNKNOWN"),
        "dataset_governance_trend_alert_count": len(trend_alerts),
        "dataset_policy_effectiveness_decision": effectiveness_decision,
    }

    reasons: list[str] = []
    score = 0

    if signals["dataset_governance_latest_status"] == "FAIL":
        reasons.append("dataset_governance_latest_fail")
        score += 3
    if signals["dataset_governance_fail_rate"] >= 0.3:
        reasons.append("dataset_governance_fail_rate_high")
        score += 2
    if signals["dataset_governance_needs_review_rate"] >= 0.4:
        reasons.append("dataset_governance_needs_review_rate_high")
        score += 2
    if signals["dataset_governance_trend_status"] == "NEEDS_REVIEW":
        reasons.append("dataset_governance_trend_needs_review")
        score += 2
    if signals["dataset_governance_trend_alert_count"] > 0:
        reasons.append("dataset_governance_trend_alerts_present")
        score += 1
    if effectiveness_decision == "ROLLBACK_REVIEW":
        reasons.append("dataset_policy_effectiveness_rollback_review")
        score += 3
    elif effectiveness_decision == "NEEDS_REVIEW":
        reasons.append("dataset_policy_effectiveness_needs_review")
        score += 1

    if score >= 6:
        suggested_profile = "dataset_strict"
        suggested_action = "tighten_generation_controls"
        confidence = 0.86
    elif score >= 3:
        suggested_profile = "dataset_default"
        suggested_action = "targeted_mutation_expansion"
        confidence = 0.74
    else:
        suggested_profile = "dataset_default"
        suggested_action = "keep"
        confidence = 0.64

    if not reasons:
        reasons.append("dataset_strategy_signals_stable")

    advice = {
        "suggested_policy_profile": suggested_profile,
        "suggested_action": suggested_action,
        "confidence": round(confidence, 2),
        "reasons": sorted(set(reasons)),
        "dry_run": True,
    }
    return advice, signals


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset strategy auto-tune advisor")
    parser.add_argument("--dataset-governance-summary", required=True, help="Path to dataset governance summary JSON")
    parser.add_argument("--dataset-governance-trend", required=True, help="Path to dataset governance trend JSON")
    parser.add_argument("--effectiveness-summary", required=True, help="Path to dataset policy effectiveness JSON")
    parser.add_argument("--out", default="artifacts/dataset_strategy_autotune/advisor.json", help="Advisor output JSON")
    parser.add_argument("--report-out", default=None, help="Advisor output markdown")
    args = parser.parse_args()

    dataset_governance = _load_json(args.dataset_governance_summary)
    dataset_governance_trend = _load_json(args.dataset_governance_trend)
    effectiveness = _load_json(args.effectiveness_summary)

    advice, signals = _build_advice(dataset_governance, dataset_governance_trend, effectiveness)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "dataset_governance_summary": args.dataset_governance_summary,
            "dataset_governance_trend": args.dataset_governance_trend,
            "effectiveness_summary": args.effectiveness_summary,
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
                "suggested_action": advice.get("suggested_action"),
                "confidence": advice.get("confidence"),
            }
        )
    )


if __name__ == "__main__":
    main()

