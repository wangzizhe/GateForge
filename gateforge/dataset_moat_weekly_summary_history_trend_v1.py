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
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Moat Weekly Summary History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- delta_avg_real_model_count: `{trend.get('delta_avg_real_model_count')}`",
        f"- delta_avg_stability_score: `{trend.get('delta_avg_stability_score')}`",
        f"- delta_avg_advantage_score: `{trend.get('delta_avg_advantage_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two moat weekly summary history snapshots")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_weekly_summary_history_trend_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    status_transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"
    delta_avg_real_model_count = round(
        _to_float(current.get("avg_real_model_count")) - _to_float(previous.get("avg_real_model_count")), 4
    )
    delta_avg_stability_score = round(
        _to_float(current.get("avg_stability_score")) - _to_float(previous.get("avg_stability_score")), 4
    )
    delta_avg_advantage_score = round(
        _to_float(current.get("avg_advantage_score")) - _to_float(previous.get("avg_advantage_score")), 4
    )

    alerts: list[str] = []
    if status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("weekly_summary_history_status_worsened")
    if delta_avg_real_model_count < 0:
        alerts.append("avg_real_model_count_decreasing")
    if delta_avg_stability_score < 0:
        alerts.append("avg_stability_score_decreasing")
    if delta_avg_advantage_score < 0:
        alerts.append("avg_advantage_score_decreasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "status_transition": status_transition,
            "delta_avg_real_model_count": delta_avg_real_model_count,
            "delta_avg_stability_score": delta_avg_stability_score,
            "delta_avg_advantage_score": delta_avg_advantage_score,
            "alerts": alerts,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
