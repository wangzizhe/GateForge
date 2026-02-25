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


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend", {}) if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Dataset History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- previous_total_records: `{payload.get('previous_total_records')}`",
        f"- current_total_records: `{payload.get('current_total_records')}`",
        f"- delta_latest_deduplicated_cases: `{trend.get('delta_latest_deduplicated_cases')}`",
        f"- delta_latest_failure_case_rate: `{trend.get('delta_latest_failure_case_rate')}`",
        f"- delta_freeze_pass_rate: `{trend.get('delta_freeze_pass_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = trend.get("alerts", []) if isinstance(trend.get("alerts"), list) else []
    if alerts:
        for a in alerts:
            lines.append(f"- `{a}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare dataset history summary against previous summary")
    parser.add_argument("--summary", required=True, help="Current dataset history summary JSON")
    parser.add_argument("--previous-summary", required=True, help="Previous dataset history summary JSON")
    parser.add_argument("--out", default="artifacts/dataset/history_trend.json", help="Trend output JSON")
    parser.add_argument("--report-out", default=None, help="Trend output markdown")
    parser.add_argument("--max-dedup-drop", type=int, default=2, help="Alert threshold for deduplicated case count drop")
    parser.add_argument(
        "--max-failure-rate-drop",
        type=float,
        default=0.05,
        help="Alert threshold for failure case rate drop",
    )
    parser.add_argument(
        "--max-freeze-pass-rate-drop",
        type=float,
        default=0.05,
        help="Alert threshold for freeze pass rate drop",
    )
    args = parser.parse_args()

    current = _load_json(args.summary)
    previous = _load_json(args.previous_summary)

    delta_latest_dedup = _to_int(current.get("latest_deduplicated_cases")) - _to_int(previous.get("latest_deduplicated_cases"))
    delta_latest_failure_rate = round(
        _to_float(current.get("latest_failure_case_rate")) - _to_float(previous.get("latest_failure_case_rate")),
        4,
    )
    delta_freeze_pass_rate = round(
        _to_float(current.get("freeze_pass_rate")) - _to_float(previous.get("freeze_pass_rate")),
        4,
    )

    alerts: list[str] = []
    if delta_latest_dedup < -abs(int(args.max_dedup_drop)):
        alerts.append("deduplicated_case_count_drop_detected")
    if delta_latest_failure_rate < -abs(float(args.max_failure_rate_drop)):
        alerts.append("failure_case_rate_drop_detected")
    if delta_freeze_pass_rate < -abs(float(args.max_freeze_pass_rate_drop)):
        alerts.append("freeze_pass_rate_drop_detected")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "previous_total_records": _to_int(previous.get("total_records")),
        "current_total_records": _to_int(current.get("total_records")),
        "trend": {
            "delta_latest_deduplicated_cases": delta_latest_dedup,
            "delta_latest_failure_case_rate": delta_latest_failure_rate,
            "delta_freeze_pass_rate": delta_freeze_pass_rate,
            "alerts": alerts,
        },
        "sources": {
            "summary": args.summary,
            "previous_summary": args.previous_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
