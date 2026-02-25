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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend", {})
    lines = [
        "# GateForge Dataset Promotion Effectiveness History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_keep_rate: `{trend.get('delta_keep_rate')}`",
        f"- delta_needs_review_rate: `{trend.get('delta_needs_review_rate')}`",
        f"- delta_rollback_review_rate: `{trend.get('delta_rollback_review_rate')}`",
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
    parser = argparse.ArgumentParser(description="Compare dataset promotion effectiveness history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_promotion_effectiveness_history/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)
    d_keep = round(_to_float(current.get("keep_rate")) - _to_float(previous.get("keep_rate")), 4)
    d_review = round(_to_float(current.get("needs_review_rate")) - _to_float(previous.get("needs_review_rate")), 4)
    d_rollback = round(
        _to_float(current.get("rollback_review_rate")) - _to_float(previous.get("rollback_review_rate")),
        4,
    )

    alerts: list[str] = []
    if d_rollback > 0:
        alerts.append("rollback_review_rate_increasing")
    if d_review > 0:
        alerts.append("needs_review_rate_increasing")
    if d_keep < 0:
        alerts.append("keep_rate_decreasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_keep_rate": d_keep,
            "delta_needs_review_rate": d_review,
            "delta_rollback_review_rate": d_rollback,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
