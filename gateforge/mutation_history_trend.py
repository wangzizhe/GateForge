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
        "# GateForge Mutation History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_match_rate: `{trend.get('delta_match_rate')}`",
        f"- delta_gate_pass_rate: `{trend.get('delta_gate_pass_rate')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = trend.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for a in alerts:
            lines.append(f"- `{a}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare mutation history summaries and emit trend deltas")
    parser.add_argument("--current", required=True, help="Current mutation history summary JSON")
    parser.add_argument("--previous", required=True, help="Previous mutation history summary JSON")
    parser.add_argument("--out", default="artifacts/mutation_history/trend.json", help="Trend JSON output")
    parser.add_argument("--report-out", default=None, help="Trend markdown output")
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    d_match = round(_to_float(current.get("latest_match_rate")) - _to_float(previous.get("latest_match_rate")), 4)
    d_gate = round(_to_float(current.get("latest_gate_pass_rate")) - _to_float(previous.get("latest_gate_pass_rate")), 4)
    alerts: list[str] = []
    if d_match < 0:
        alerts.append("match_rate_regression_detected")
    if d_gate < 0:
        alerts.append("gate_pass_rate_regression_detected")
    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_match_rate": d_match,
            "delta_gate_pass_rate": d_gate,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
