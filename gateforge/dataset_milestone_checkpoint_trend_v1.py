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


def _compute(current: dict, previous: dict) -> dict:
    cs = _to_float(current.get("checkpoint_score", 0.0))
    ps = _to_float(previous.get("checkpoint_score", 0.0))
    delta = round(cs - ps, 2)
    transition = f"{previous.get('status', 'UNKNOWN')}->{current.get('status', 'UNKNOWN')}"

    alerts: list[str] = []
    if delta < -5:
        alerts.append("checkpoint_score_drop_significant")
    if transition in {"PASS->NEEDS_REVIEW", "PASS->FAIL", "NEEDS_REVIEW->FAIL"}:
        alerts.append("status_worsened")
    if str(current.get("milestone_decision") or "") == "HOLD":
        alerts.append("milestone_hold")

    return {
        "status_transition": transition,
        "checkpoint_score_delta": delta,
        "alerts": alerts,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    trend = payload.get("trend") if isinstance(payload.get("trend"), dict) else {}
    lines = [
        "# GateForge Milestone Checkpoint Trend v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- status_transition: `{trend.get('status_transition')}`",
        f"- checkpoint_score_delta: `{trend.get('checkpoint_score_delta')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute milestone checkpoint trend")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--previous-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_milestone_checkpoint_trend_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current = _load_json(args.summary)
    previous = _load_json(args.previous_summary)
    trend = _compute(current, previous)
    payload = {
        **current,
        "trend": trend,
        "sources": {
            **(current.get("sources") if isinstance(current.get("sources"), dict) else {}),
            "previous_summary": args.previous_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "status_transition": trend.get("status_transition")}))
    if payload.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
