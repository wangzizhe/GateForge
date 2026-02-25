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


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _advise(snapshot: dict, apply_history: dict, apply_history_trend: dict) -> dict:
    snapshot_status = str(snapshot.get("status") or "UNKNOWN")
    snapshot_risks = snapshot.get("risks") if isinstance(snapshot.get("risks"), list) else []
    apply_latest_status = str(apply_history.get("latest_final_status") or "UNKNOWN")
    apply_fail_rate = _to_float(apply_history.get("fail_rate", 0.0))
    apply_needs_review_rate = _to_float(apply_history.get("needs_review_rate", 0.0))
    apply_trend_status = str(apply_history_trend.get("status") or "UNKNOWN")

    reasons: list[str] = []
    confidence = 0.62
    decision = "HOLD"
    action = "hold_for_review"

    if snapshot_status == "FAIL":
        reasons.append("snapshot_fail")
        decision = "BLOCK"
        action = "block_release"
        confidence = 0.92
    if apply_latest_status == "FAIL":
        reasons.append("strategy_apply_latest_fail")
        decision = "BLOCK"
        action = "block_release"
        confidence = max(confidence, 0.9)
    if apply_fail_rate >= 0.4:
        reasons.append("strategy_apply_fail_rate_high")
        decision = "BLOCK"
        action = "block_release"
        confidence = max(confidence, 0.88)

    if decision != "BLOCK":
        if snapshot_status == "NEEDS_REVIEW":
            reasons.append("snapshot_needs_review")
            decision = "HOLD"
            action = "hold_for_review"
            confidence = max(confidence, 0.78)
        if apply_trend_status == "NEEDS_REVIEW":
            reasons.append("strategy_apply_trend_needs_review")
            decision = "HOLD"
            action = "hold_for_review"
            confidence = max(confidence, 0.8)
        if apply_needs_review_rate >= 0.35:
            reasons.append("strategy_apply_needs_review_rate_high")
            decision = "HOLD"
            action = "hold_for_review"
            confidence = max(confidence, 0.76)
        if not reasons and snapshot_status == "PASS" and apply_trend_status == "PASS":
            decision = "PROMOTE"
            action = "promote_candidate"
            confidence = 0.86
            reasons.append("signals_stable")

    # If we already have stability rationale but also many risks, downgrade.
    if decision == "PROMOTE" and len(snapshot_risks) > 0:
        decision = "HOLD"
        action = "hold_for_review"
        reasons = [r for r in reasons if r != "signals_stable"]
        reasons.append("snapshot_risks_present")
        confidence = 0.74

    if not reasons:
        reasons.append("insufficient_signals_hold")

    return {
        "decision": decision,
        "action": action,
        "confidence": round(confidence, 2),
        "reasons": sorted(set(reasons)),
        "dry_run": True,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice", {})
    lines = [
        "# GateForge Dataset Promotion Candidate Advisor",
        "",
        f"- decision: `{advice.get('decision')}`",
        f"- action: `{advice.get('action')}`",
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
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend promotion decision from dataset governance signals")
    parser.add_argument("--snapshot", required=True, help="Dataset governance snapshot summary JSON")
    parser.add_argument("--strategy-apply-history", required=True, help="Dataset strategy apply history summary JSON")
    parser.add_argument(
        "--strategy-apply-history-trend",
        required=True,
        help="Dataset strategy apply history trend JSON",
    )
    parser.add_argument("--out", default="artifacts/dataset_promotion_candidate/advisor.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    snapshot = _load_json(args.snapshot)
    apply_history = _load_json(args.strategy_apply_history)
    apply_history_trend = _load_json(args.strategy_apply_history_trend)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "snapshot_path": args.snapshot,
            "strategy_apply_history_path": args.strategy_apply_history,
            "strategy_apply_history_trend_path": args.strategy_apply_history_trend,
        },
        "advice": _advise(snapshot, apply_history, apply_history_trend),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "decision": payload["advice"].get("decision"),
                "action": payload["advice"].get("action"),
                "confidence": payload["advice"].get("confidence"),
            }
        )
    )


if __name__ == "__main__":
    main()
