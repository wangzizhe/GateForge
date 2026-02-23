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
        "# GateForge Medium Benchmark Advisor",
        "",
        f"- suggested_profile: `{advice.get('suggested_profile')}`",
        f"- decision: `{advice.get('decision')}`",
        f"- confidence: `{advice.get('confidence')}`",
        f"- action: `{advice.get('action')}`",
        "",
        "## Reasons",
        "",
    ]
    reasons = advice.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Advise medium benchmark governance profile from history and trend")
    parser.add_argument(
        "--history-summary",
        default="artifacts/benchmark_medium_v1/history_summary.json",
        help="medium benchmark history summary json",
    )
    parser.add_argument(
        "--trend-summary",
        default="artifacts/benchmark_medium_v1/history_trend.json",
        help="medium benchmark history trend json",
    )
    parser.add_argument("--out", default="artifacts/benchmark_medium_v1/advisor.json", help="advisor summary JSON path")
    parser.add_argument("--report-out", default=None, help="advisor markdown output path")
    args = parser.parse_args()

    history = _load_json(args.history_summary)
    trend_payload = _load_json(args.trend_summary)
    trend = trend_payload.get("trend", {}) if isinstance(trend_payload.get("trend"), dict) else {}
    history_alerts = history.get("alerts", []) if isinstance(history.get("alerts"), list) else []
    trend_alerts = trend_payload.get("trend_alerts", []) if isinstance(trend_payload.get("trend_alerts"), list) else []

    latest_pass_rate = float(history.get("latest_pass_rate", 0.0) or 0.0)
    avg_pass_rate = float(history.get("avg_pass_rate", 0.0) or 0.0)
    delta_pass_rate = float(trend.get("delta_pass_rate", 0.0) or 0.0)
    mismatch_total = int(history.get("mismatch_case_total", 0) or 0)
    reasons: list[str] = []

    if latest_pass_rate < 0.9:
        reasons.append("latest_pass_rate_below_target")
    if avg_pass_rate < 0.95:
        reasons.append("average_pass_rate_below_target")
    if delta_pass_rate <= -0.05:
        reasons.append("pass_rate_regression_detected")
    if mismatch_total >= 1:
        reasons.append("mismatch_cases_present")
    for a in history_alerts:
        reasons.append(f"history_alert:{a}")
    for a in trend_alerts:
        reasons.append(f"trend_alert:{a}")

    if reasons:
        suggested_profile = "industrial_strict_v0"
        decision = "TIGHTEN"
        action = "raise review strictness and investigate mismatch roots"
        confidence = 0.85
    else:
        suggested_profile = "default"
        decision = "KEEP"
        action = "keep current profile and continue monitoring"
        confidence = 0.75

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "history_summary_path": args.history_summary,
        "trend_summary_path": args.trend_summary,
        "kpis": {
            "latest_pass_rate": latest_pass_rate,
            "avg_pass_rate": avg_pass_rate,
            "delta_pass_rate": delta_pass_rate,
            "mismatch_case_total": mismatch_total,
        },
        "advice": {
            "suggested_profile": suggested_profile,
            "decision": decision,
            "action": action,
            "confidence": confidence,
            "reasons": sorted(set(reasons)),
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "decision": decision,
                "suggested_profile": suggested_profile,
                "reasons_count": len(payload["advice"]["reasons"]),
            }
        )
    )


if __name__ == "__main__":
    main()
