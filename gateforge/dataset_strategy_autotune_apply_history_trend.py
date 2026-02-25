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


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend", {})
    lines = [
        "# GateForge Dataset Strategy Apply History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_pass_rate: `{trend.get('delta_pass_rate')}`",
        f"- delta_needs_review_rate: `{trend.get('delta_needs_review_rate')}`",
        f"- delta_fail_rate: `{trend.get('delta_fail_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = trend.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare dataset strategy apply history summaries and emit trend deltas")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_strategy_apply_history/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)
    d_pass = round(_to_float(current.get("pass_rate")) - _to_float(previous.get("pass_rate")), 4)
    d_review = round(_to_float(current.get("needs_review_rate")) - _to_float(previous.get("needs_review_rate")), 4)
    d_fail = round(_to_float(current.get("fail_rate")) - _to_float(previous.get("fail_rate")), 4)

    alerts: list[str] = []
    if d_fail > 0:
        alerts.append("apply_fail_rate_increasing")
    if d_review > 0:
        alerts.append("apply_needs_review_rate_increasing")
    if d_pass < 0:
        alerts.append("apply_pass_rate_decreasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_pass_rate": d_pass,
            "delta_needs_review_rate": d_review,
            "delta_fail_rate": d_fail,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
