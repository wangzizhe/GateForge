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


def _to_int(v: object) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend", {})
    lines = [
        "# GateForge Runtime Ledger History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_total_records: `{trend.get('delta_total_records')}`",
        f"- delta_avg_pass_rate: `{trend.get('delta_avg_pass_rate')}`",
        f"- delta_avg_fail_rate: `{trend.get('delta_avg_fail_rate')}`",
        f"- delta_avg_needs_review_rate: `{trend.get('delta_avg_needs_review_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = trend.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        lines.extend([f"- `{a}`" for a in alerts])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare runtime-ledger history summaries and emit trend deltas")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/governance_runtime/history_trend.json")
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--fail-rate-delta-alert", type=float, default=0.05)
    parser.add_argument("--needs-review-rate-delta-alert", type=float, default=0.05)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    delta_total_records = _to_int(current.get("total_records")) - _to_int(previous.get("total_records"))
    delta_avg_pass_rate = round(_to_float(current.get("avg_pass_rate")) - _to_float(previous.get("avg_pass_rate")), 4)
    delta_avg_fail_rate = round(_to_float(current.get("avg_fail_rate")) - _to_float(previous.get("avg_fail_rate")), 4)
    delta_avg_needs_review_rate = round(
        _to_float(current.get("avg_needs_review_rate")) - _to_float(previous.get("avg_needs_review_rate")), 4
    )

    alerts: list[str] = []
    if delta_avg_fail_rate > float(args.fail_rate_delta_alert):
        alerts.append("avg_fail_rate_increasing")
    if delta_avg_needs_review_rate > float(args.needs_review_rate_delta_alert):
        alerts.append("avg_needs_review_rate_increasing")
    if delta_avg_pass_rate < -float(args.fail_rate_delta_alert):
        alerts.append("avg_pass_rate_regression_detected")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_total_records": delta_total_records,
            "delta_avg_pass_rate": delta_avg_pass_rate,
            "delta_avg_fail_rate": delta_avg_fail_rate,
            "delta_avg_needs_review_rate": delta_avg_needs_review_rate,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
