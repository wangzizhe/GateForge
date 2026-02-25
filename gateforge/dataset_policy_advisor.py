from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DATASET_POLICY_DIR = Path("policies/dataset")


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


def _resolve_policy_path(policy_path: str | None, profile: str | None) -> str:
    if policy_path and profile:
        raise ValueError("Use either --policy-path or --policy-profile, not both")
    if profile:
        name = profile if profile.endswith(".json") else f"{profile}.json"
        resolved = DATASET_POLICY_DIR / name
        if not resolved.exists():
            raise ValueError(f"Dataset policy profile not found: {resolved}")
        return str(resolved)
    if policy_path:
        return policy_path
    return str(DATASET_POLICY_DIR / "default.json")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice", {}) if isinstance(payload.get("advice"), dict) else {}
    lines = [
        "# GateForge Dataset Policy Advisor",
        "",
        f"- suggested_action: `{advice.get('suggested_action')}`",
        f"- suggested_policy_profile: `{advice.get('suggested_policy_profile')}`",
        f"- confidence: `{advice.get('confidence')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons") if isinstance(advice.get("reasons"), list) else []
    if reasons:
        for r in reasons:
            lines.append(f"- `{r}`")
    else:
        lines.append("- `none`")
    lines.extend(["", "## Signals", ""])
    signals = payload.get("signals", {}) if isinstance(payload.get("signals"), dict) else {}
    for k in sorted(signals.keys()):
        lines.append(f"- {k}: `{signals[k]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _build_advice(dataset_history: dict, dataset_history_trend: dict, policy: dict) -> tuple[dict, dict]:
    max_trend_alerts = _to_int(policy.get("max_trend_alerts", 0))
    min_cases = _to_int(policy.get("min_deduplicated_cases", 10))
    min_failure_rate = _to_float(policy.get("min_failure_case_rate", 0.2))
    min_freeze_pass_rate = _to_float(policy.get("min_freeze_pass_rate", 1.0))

    history_alerts = dataset_history.get("alerts") if isinstance(dataset_history.get("alerts"), list) else []
    trend_obj = dataset_history_trend.get("trend") if isinstance(dataset_history_trend.get("trend"), dict) else {}
    trend_alerts = trend_obj.get("alerts") if isinstance(trend_obj.get("alerts"), list) else []

    signals = {
        "latest_deduplicated_cases": _to_int(dataset_history.get("latest_deduplicated_cases", 0)),
        "latest_failure_case_rate": _to_float(dataset_history.get("latest_failure_case_rate", 0.0)),
        "freeze_pass_rate": _to_float(dataset_history.get("freeze_pass_rate", 0.0)),
        "history_alert_count": len(history_alerts),
        "trend_status": str(dataset_history_trend.get("status") or "UNKNOWN"),
        "trend_alert_count": len(trend_alerts),
    }

    reasons: list[str] = []
    score = 0
    threshold_patch: dict[str, int | float | None] = {
        "min_deduplicated_cases": None,
        "min_failure_case_rate": None,
    }

    if signals["latest_deduplicated_cases"] < min_cases:
        reasons.append("dataset_case_count_below_policy")
        score += 2
        threshold_patch["min_deduplicated_cases"] = min_cases + 2

    if signals["latest_failure_case_rate"] < min_failure_rate:
        reasons.append("dataset_failure_coverage_below_policy")
        score += 2
        threshold_patch["min_failure_case_rate"] = round(min_failure_rate, 3)

    if signals["freeze_pass_rate"] < min_freeze_pass_rate:
        reasons.append("dataset_freeze_pass_rate_below_policy")
        score += 2

    if signals["history_alert_count"] > 0:
        reasons.append("dataset_history_alerts_present")
        score += 1

    if signals["trend_status"] == "NEEDS_REVIEW":
        reasons.append("dataset_history_trend_needs_review")
        score += 2

    if signals["trend_alert_count"] > max_trend_alerts:
        reasons.append("dataset_trend_alert_budget_exceeded")
        score += 2

    if score >= 5:
        action = str(policy.get("action_on_trend_regression") or "hold_release")
        profile = "dataset_strict"
        confidence = 0.86
    elif score >= 2:
        action = str(policy.get("action_on_low_case_count") or "expand_mutation")
        profile = "dataset_default"
        confidence = 0.72
    else:
        action = "keep"
        profile = "dataset_default"
        confidence = 0.63

    if not reasons:
        reasons.append("dataset_signals_stable")

    advice = {
        "suggested_action": action,
        "suggested_policy_profile": profile,
        "confidence": round(confidence, 2),
        "reasons": sorted(set(reasons)),
        "threshold_patch": threshold_patch,
        "dry_run": True,
    }
    return advice, signals


def main() -> None:
    parser = argparse.ArgumentParser(description="Dataset policy advisor from dataset history/trend summaries")
    parser.add_argument("--dataset-history-summary", required=True, help="Path to dataset history summary JSON")
    parser.add_argument("--dataset-history-trend", required=True, help="Path to dataset history trend JSON")
    parser.add_argument("--policy-path", default=None, help="Dataset policy path")
    parser.add_argument("--policy-profile", default=None, help="Dataset policy profile name")
    parser.add_argument("--out", default="artifacts/dataset_policy/advisor.json", help="Advisor output JSON")
    parser.add_argument("--report-out", default=None, help="Advisor output markdown")
    args = parser.parse_args()

    policy_path = _resolve_policy_path(args.policy_path, args.policy_profile)
    policy = _load_json(policy_path)
    history = _load_json(args.dataset_history_summary)
    trend = _load_json(args.dataset_history_trend)

    advice, signals = _build_advice(history, trend, policy)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "dataset_history_summary": args.dataset_history_summary,
            "dataset_history_trend": args.dataset_history_trend,
            "policy_path": policy_path,
        },
        "advice": advice,
        "signals": signals,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "suggested_action": advice.get("suggested_action"),
                "suggested_policy_profile": advice.get("suggested_policy_profile"),
                "confidence": advice.get("confidence"),
            }
        )
    )


if __name__ == "__main__":
    main()
