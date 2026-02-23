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
    trend = payload.get("trend", {})
    lines = [
        "# GateForge Medium Benchmark History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- current_total_records: `{payload.get('current_total_records')}`",
        f"- previous_total_records: `{payload.get('previous_total_records')}`",
        f"- delta_total_records: `{trend.get('delta_total_records')}`",
        f"- current_pass_rate: `{trend.get('current_pass_rate')}`",
        f"- previous_pass_rate: `{trend.get('previous_pass_rate')}`",
        f"- delta_pass_rate: `{trend.get('delta_pass_rate')}`",
        f"- current_mismatch_case_total: `{trend.get('current_mismatch_case_total')}`",
        f"- previous_mismatch_case_total: `{trend.get('previous_mismatch_case_total')}`",
        f"- delta_mismatch_case_total: `{trend.get('delta_mismatch_case_total')}`",
        "",
        "## Trend Alerts",
        "",
    ]
    alerts = payload.get("trend_alerts", [])
    if isinstance(alerts, list) and alerts:
        for a in alerts:
            lines.append(f"- {a}")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute trend deltas for medium benchmark history summaries")
    parser.add_argument("--summary", required=True, help="Current medium history summary JSON path")
    parser.add_argument("--previous-summary", default=None, help="Previous medium history summary JSON path")
    parser.add_argument(
        "--out",
        default="artifacts/benchmark_medium_v1/history_trend.json",
        help="Trend JSON output path",
    )
    parser.add_argument("--report-out", default=None, help="Trend markdown output path")
    parser.add_argument(
        "--degrade-pass-rate-threshold",
        type=float,
        default=-0.05,
        help="Alert when delta pass rate <= this threshold",
    )
    parser.add_argument(
        "--mismatch-growth-threshold",
        type=int,
        default=1,
        help="Alert when mismatch-case total grows by at least this amount",
    )
    args = parser.parse_args()

    current = _load_json(args.summary)
    previous = _load_json(args.previous_summary) if args.previous_summary else {}
    current_total = int(current.get("total_records", 0) or 0)
    previous_total = int(previous.get("total_records", 0) or 0)
    current_pass_rate = float(current.get("latest_pass_rate", 0.0) or 0.0)
    previous_pass_rate = float(previous.get("latest_pass_rate", 0.0) or 0.0)
    current_mismatch_total = int(current.get("mismatch_case_total", 0) or 0)
    previous_mismatch_total = int(previous.get("mismatch_case_total", 0) or 0)
    delta_pass_rate = round(current_pass_rate - previous_pass_rate, 4)
    delta_mismatch_total = current_mismatch_total - previous_mismatch_total
    trend_alerts: list[str] = []
    if delta_pass_rate <= args.degrade_pass_rate_threshold:
        trend_alerts.append("pass_rate_regression_detected")
    if delta_mismatch_total >= max(1, int(args.mismatch_growth_threshold)):
        trend_alerts.append("mismatch_case_growth_detected")

    trend = {
        "delta_total_records": current_total - previous_total,
        "current_pass_rate": current_pass_rate,
        "previous_pass_rate": previous_pass_rate,
        "delta_pass_rate": delta_pass_rate,
        "current_mismatch_case_total": current_mismatch_total,
        "previous_mismatch_case_total": previous_mismatch_total,
        "delta_mismatch_case_total": delta_mismatch_total,
    }
    payload = {
        "status": current.get("latest_pack_id"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_path": args.summary,
        "previous_summary_path": args.previous_summary,
        "current_total_records": current_total,
        "previous_total_records": previous_total,
        "trend": trend,
        "trend_alerts": trend_alerts,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"delta_pass_rate": delta_pass_rate, "trend_alerts": trend_alerts}))


if __name__ == "__main__":
    main()
