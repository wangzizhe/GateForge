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
        "# GateForge Intake Growth Execution Board History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- latest_board_status_transition: `{trend.get('latest_board_status_transition')}`",
        f"- delta_avg_execution_score: `{trend.get('delta_avg_execution_score')}`",
        f"- delta_critical_open_tasks_rate: `{trend.get('delta_critical_open_tasks_rate')}`",
        f"- delta_avg_projected_weeks_to_target: `{trend.get('delta_avg_projected_weeks_to_target')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = trend.get("alerts") if isinstance(trend.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare intake growth execution board history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_intake_growth_execution_board_history_v1/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    status_transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"
    latest_board_status_transition = (
        f"{previous.get('latest_board_status', 'UNKNOWN')}->{current.get('latest_board_status', 'UNKNOWN')}"
    )
    delta_avg_execution_score = round(
        _to_float(current.get("avg_execution_score")) - _to_float(previous.get("avg_execution_score")), 4
    )
    delta_critical_open_tasks_rate = round(
        _to_float(current.get("critical_open_tasks_rate")) - _to_float(previous.get("critical_open_tasks_rate")), 4
    )
    delta_avg_projected_weeks_to_target = round(
        _to_float(current.get("avg_projected_weeks_to_target"))
        - _to_float(previous.get("avg_projected_weeks_to_target")),
        4,
    )

    alerts: list[str] = []
    if status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("execution_board_history_status_worsened")
    if latest_board_status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("latest_board_status_worsened")
    if delta_avg_execution_score < 0:
        alerts.append("avg_execution_score_decreasing")
    if delta_critical_open_tasks_rate > 0:
        alerts.append("critical_open_tasks_rate_increasing")
    if delta_avg_projected_weeks_to_target > 0:
        alerts.append("projected_weeks_to_target_increasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "status_transition": status_transition,
            "latest_board_status_transition": latest_board_status_transition,
            "delta_avg_execution_score": delta_avg_execution_score,
            "delta_critical_open_tasks_rate": delta_critical_open_tasks_rate,
            "delta_avg_projected_weeks_to_target": delta_avg_projected_weeks_to_target,
            "alerts": alerts,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
