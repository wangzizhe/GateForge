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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    alerts = payload.get("alerts", [])
    lines = [
        "# GateForge Runtime Ledger Trend",
        "",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        f"- status: `{payload.get('status')}`",
        f"- delta_total_records: `{payload.get('delta', {}).get('total_records')}`",
        f"- delta_pass_rate: `{payload.get('delta', {}).get('pass_rate')}`",
        f"- delta_fail_rate: `{payload.get('delta', {}).get('fail_rate')}`",
        f"- delta_needs_review_rate: `{payload.get('delta', {}).get('needs_review_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    if alerts:
        lines.extend([f"- `{a}`" for a in alerts])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def analyze_trend(
    current: dict,
    previous: dict,
    *,
    fail_rate_alert_delta: float = 0.05,
    needs_review_alert_delta: float = 0.05,
) -> dict:
    cur_kpis = current.get("kpis", {}) if isinstance(current, dict) else {}
    prev_kpis = previous.get("kpis", {}) if isinstance(previous, dict) else {}
    cur_total = int(current.get("total_records", 0) or 0)
    prev_total = int(previous.get("total_records", 0) or 0)

    cur_pass = float(cur_kpis.get("pass_rate", 0.0) or 0.0)
    cur_fail = float(cur_kpis.get("fail_rate", 0.0) or 0.0)
    cur_review = float(cur_kpis.get("needs_review_rate", 0.0) or 0.0)
    prev_pass = float(prev_kpis.get("pass_rate", 0.0) or 0.0)
    prev_fail = float(prev_kpis.get("fail_rate", 0.0) or 0.0)
    prev_review = float(prev_kpis.get("needs_review_rate", 0.0) or 0.0)

    delta = {
        "total_records": cur_total - prev_total,
        "pass_rate": round(cur_pass - prev_pass, 4),
        "fail_rate": round(cur_fail - prev_fail, 4),
        "needs_review_rate": round(cur_review - prev_review, 4),
    }
    alerts: list[str] = []
    if delta["fail_rate"] > fail_rate_alert_delta:
        alerts.append("fail_rate_regression_detected")
    if delta["needs_review_rate"] > needs_review_alert_delta:
        alerts.append("needs_review_rate_growth_detected")
    if delta["pass_rate"] < -fail_rate_alert_delta:
        alerts.append("pass_rate_regression_detected")

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not alerts else "NEEDS_REVIEW",
        "alerts": alerts,
        "thresholds": {
            "fail_rate_alert_delta": fail_rate_alert_delta,
            "needs_review_alert_delta": needs_review_alert_delta,
        },
        "delta": delta,
        "current_total_records": cur_total,
        "previous_total_records": prev_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze runtime ledger summary trend")
    parser.add_argument("--current", required=True, help="Current runtime ledger summary JSON")
    parser.add_argument("--previous", default=None, help="Previous runtime ledger summary JSON")
    parser.add_argument("--fail-rate-alert-delta", type=float, default=0.05)
    parser.add_argument("--needs-review-alert-delta", type=float, default=0.05)
    parser.add_argument("--out", default="artifacts/governance_runtime/ledger_trend.json")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)
    trend = analyze_trend(
        current=current,
        previous=previous,
        fail_rate_alert_delta=float(args.fail_rate_alert_delta),
        needs_review_alert_delta=float(args.needs_review_alert_delta),
    )
    _write_json(args.out, trend)
    report = args.report
    if not report:
        out = Path(args.out)
        report = str(out.with_suffix(".md")) if out.suffix == ".json" else f"{args.out}.md"
    _write_markdown(report, trend)
    print(json.dumps({"status": trend["status"], "alerts": trend["alerts"]}))
    if trend["status"] == "NEEDS_REVIEW":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
