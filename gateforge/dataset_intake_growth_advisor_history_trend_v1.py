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
        "# GateForge Intake Growth Advisor History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- latest_action_transition: `{trend.get('latest_action_transition')}`",
        f"- delta_recovery_plan_rate: `{trend.get('delta_recovery_plan_rate')}`",
        f"- delta_avg_backlog_action_count: `{trend.get('delta_avg_backlog_action_count')}`",
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
    parser = argparse.ArgumentParser(description="Compare intake growth advisor history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_intake_growth_advisor_history_v1/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    status_transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"
    latest_action_transition = (
        f"{previous.get('latest_suggested_action', 'unknown')}->{current.get('latest_suggested_action', 'unknown')}"
    )
    delta_recovery_plan_rate = round(
        _to_float(current.get("recovery_plan_rate")) - _to_float(previous.get("recovery_plan_rate")), 4
    )
    delta_targeted_patch_rate = round(
        _to_float(current.get("targeted_patch_rate")) - _to_float(previous.get("targeted_patch_rate")), 4
    )
    delta_avg_backlog_action_count = round(
        _to_float(current.get("avg_backlog_action_count")) - _to_float(previous.get("avg_backlog_action_count")), 4
    )

    alerts: list[str] = []
    if status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("intake_growth_history_status_worsened")
    if latest_action_transition in {
        "keep->execute_targeted_growth_patch",
        "keep->execute_growth_recovery_plan",
        "execute_targeted_growth_patch->execute_growth_recovery_plan",
    }:
        alerts.append("intake_growth_latest_action_worsened")
    if delta_recovery_plan_rate > 0:
        alerts.append("recovery_plan_rate_increasing")
    if delta_avg_backlog_action_count > 0:
        alerts.append("avg_backlog_action_count_increasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "status_transition": status_transition,
            "latest_action_transition": latest_action_transition,
            "delta_recovery_plan_rate": delta_recovery_plan_rate,
            "delta_targeted_patch_rate": delta_targeted_patch_rate,
            "delta_avg_backlog_action_count": delta_avg_backlog_action_count,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
