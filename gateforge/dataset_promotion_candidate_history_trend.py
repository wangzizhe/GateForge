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
        "# GateForge Dataset Promotion Candidate History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_promote_rate: `{trend.get('delta_promote_rate')}`",
        f"- delta_hold_rate: `{trend.get('delta_hold_rate')}`",
        f"- delta_block_rate: `{trend.get('delta_block_rate')}`",
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
    parser = argparse.ArgumentParser(description="Compare dataset promotion candidate history summaries and emit trend deltas")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_promotion_candidate_history/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)
    d_promote = round(_to_float(current.get("promote_rate")) - _to_float(previous.get("promote_rate")), 4)
    d_hold = round(_to_float(current.get("hold_rate")) - _to_float(previous.get("hold_rate")), 4)
    d_block = round(_to_float(current.get("block_rate")) - _to_float(previous.get("block_rate")), 4)

    alerts: list[str] = []
    if d_block > 0:
        alerts.append("block_rate_increasing")
    if d_hold > 0:
        alerts.append("hold_rate_increasing")
    if d_promote < 0:
        alerts.append("promote_rate_decreasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_promote_rate": d_promote,
            "delta_hold_rate": d_hold,
            "delta_block_rate": d_block,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
