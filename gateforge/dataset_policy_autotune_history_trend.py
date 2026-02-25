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
        "# GateForge Dataset Policy Auto-Tune History Trend",
        "",
        f"- status: `{payload.get('status')}`",
        f"- delta_strict_suggestion_rate: `{trend.get('delta_strict_suggestion_rate')}`",
        f"- delta_avg_confidence: `{trend.get('delta_avg_confidence')}`",
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
    parser = argparse.ArgumentParser(description="Compare dataset policy autotune history summaries and emit trend deltas")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_policy_autotune_history/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    d_strict = round(
        _to_float(current.get("strict_suggestion_rate")) - _to_float(previous.get("strict_suggestion_rate")),
        4,
    )
    d_conf = round(_to_float(current.get("avg_confidence")) - _to_float(previous.get("avg_confidence")), 4)
    alerts: list[str] = []
    if d_strict > 0:
        alerts.append("strict_suggestion_rate_increasing")
    if d_conf < 0:
        alerts.append("avg_confidence_decreasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "delta_strict_suggestion_rate": d_strict,
            "delta_avg_confidence": d_conf,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()

