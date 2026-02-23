from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    advice = payload.get("advice", {})
    lines = [
        "# GateForge Policy Patch Rollback Advisor",
        "",
        f"- decision: `{advice.get('decision')}`",
        f"- confidence: `{advice.get('confidence')}`",
        f"- rollback_recommended: `{advice.get('rollback_recommended')}`",
        f"- latest_status: `{payload.get('latest_status')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for reason in reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Suggest rollback/keep decision from policy patch history trend")
    parser.add_argument("--summary", required=True, help="Policy patch history summary JSON")
    parser.add_argument("--trend", required=True, help="Policy patch history trend JSON")
    parser.add_argument("--max-fail-rate", type=float, default=0.30, help="Max acceptable fail rate")
    parser.add_argument("--max-reject-rate", type=float, default=0.30, help="Max acceptable reject rate")
    parser.add_argument("--max-fail-rate-delta", type=float, default=0.15, help="Max acceptable fail-rate increase")
    parser.add_argument("--max-reject-rate-delta", type=float, default=0.15, help="Max acceptable reject-rate increase")
    parser.add_argument(
        "--require-non-fail-latest-status",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If enabled, latest FAIL status triggers rollback recommendation",
    )
    parser.add_argument(
        "--out",
        default="artifacts/governance_policy_patch_rollback_advisor/summary.json",
        help="Advisor summary JSON path",
    )
    parser.add_argument("--report", default=None, help="Advisor markdown path")
    args = parser.parse_args()

    summary = _load_json(args.summary)
    trend_payload = _load_json(args.trend)
    trend = trend_payload.get("trend", {}) if isinstance(trend_payload.get("trend"), dict) else {}

    latest_status = str(summary.get("latest_status") or "")
    current_fail_rate = float(trend.get("current_fail_rate", 0.0) or 0.0)
    current_reject_rate = float(trend.get("current_reject_rate", 0.0) or 0.0)
    delta_fail_rate = float(trend.get("delta_fail_rate", 0.0) or 0.0)
    delta_reject_rate = float(trend.get("delta_reject_rate", 0.0) or 0.0)
    reasons: list[str] = []

    if args.require_non_fail_latest_status and latest_status == "FAIL":
        reasons.append("latest_status_fail")
    if current_fail_rate > args.max_fail_rate:
        reasons.append(f"fail_rate_high:{current_fail_rate:.4f}>{args.max_fail_rate:.4f}")
    if current_reject_rate > args.max_reject_rate:
        reasons.append(f"reject_rate_high:{current_reject_rate:.4f}>{args.max_reject_rate:.4f}")
    if delta_fail_rate > args.max_fail_rate_delta:
        reasons.append(f"fail_rate_delta_high:{delta_fail_rate:.4f}>{args.max_fail_rate_delta:.4f}")
    if delta_reject_rate > args.max_reject_rate_delta:
        reasons.append(f"reject_rate_delta_high:{delta_reject_rate:.4f}>{args.max_reject_rate_delta:.4f}")

    rollback_recommended = bool(reasons)
    decision = "ROLLBACK_RECOMMENDED" if rollback_recommended else "KEEP"
    confidence = 0.85 if rollback_recommended else 0.75

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_path": args.summary,
        "trend_path": args.trend,
        "latest_status": latest_status,
        "metrics": {
            "current_fail_rate": current_fail_rate,
            "current_reject_rate": current_reject_rate,
            "delta_fail_rate": delta_fail_rate,
            "delta_reject_rate": delta_reject_rate,
        },
        "thresholds": {
            "max_fail_rate": args.max_fail_rate,
            "max_reject_rate": args.max_reject_rate,
            "max_fail_rate_delta": args.max_fail_rate_delta,
            "max_reject_rate_delta": args.max_reject_rate_delta,
            "require_non_fail_latest_status": args.require_non_fail_latest_status,
        },
        "advice": {
            "decision": decision,
            "rollback_recommended": rollback_recommended,
            "confidence": confidence,
            "reasons": reasons,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report or _default_md_path(args.out), payload)
    print(json.dumps({"decision": decision, "rollback_recommended": rollback_recommended}))


if __name__ == "__main__":
    main()
