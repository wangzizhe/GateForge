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
        "# GateForge Moat Anchor Brief History Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- recommendation_transition: `{trend.get('recommendation_transition')}`",
        f"- delta_avg_anchor_brief_score: `{trend.get('delta_avg_anchor_brief_score')}`",
        f"- delta_publish_rate: `{trend.get('delta_publish_rate')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare moat anchor brief history summaries and emit trend")
    parser.add_argument("--current", required=True)
    parser.add_argument("--previous", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_anchor_brief_history_v1/trend.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.current)
    previous = _load_json(args.previous)

    status_transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"
    recommendation_transition = (
        f"{previous.get('latest_recommendation', 'unknown')}->{current.get('latest_recommendation', 'unknown')}"
    )
    delta_avg_score = round(
        _to_float(current.get("avg_anchor_brief_score")) - _to_float(previous.get("avg_anchor_brief_score")), 4
    )
    delta_publish_rate = round(_to_float(current.get("publish_rate")) - _to_float(previous.get("publish_rate")), 4)

    alerts: list[str] = []
    if status_transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("anchor_brief_history_status_worsened")
    if recommendation_transition in {"PUBLISH->PUBLISH_WITH_GUARDS", "PUBLISH->HOLD", "PUBLISH_WITH_GUARDS->HOLD"}:
        alerts.append("anchor_recommendation_worsened")
    if delta_avg_score < 0:
        alerts.append("avg_anchor_brief_score_decreasing")
    if delta_publish_rate < 0:
        alerts.append("publish_rate_decreasing")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    payload = {
        "status": status,
        "trend": {
            "status_transition": status_transition,
            "recommendation_transition": recommendation_transition,
            "delta_avg_anchor_brief_score": delta_avg_score,
            "delta_publish_rate": delta_publish_rate,
            "alerts": alerts,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alerts": alerts}))


if __name__ == "__main__":
    main()
