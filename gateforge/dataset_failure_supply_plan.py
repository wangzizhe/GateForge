from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Supply Plan",
        "",
        f"- status: `{payload.get('status')}`",
        f"- weekly_supply_target: `{payload.get('weekly_supply_target')}`",
        f"- large_supply_target: `{payload.get('large_supply_target')}`",
        f"- medium_supply_target: `{payload.get('medium_supply_target')}`",
        f"- target_gap_supply_pressure_index: `{payload.get('target_gap_supply_pressure_index')}`",
        f"- target_gap_pressure_index: `{payload.get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{payload.get('model_asset_target_gap_score')}`",
        "",
        "## Channels",
        "",
    ]
    for row in payload.get("channels") if isinstance(payload.get("channels"), list) else []:
        lines.append(f"- `{row.get('channel')}` target=`{row.get('target_cases')}` source=`{row.get('source')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan weekly failure-case supply from queue and campaign signals")
    parser.add_argument("--large-model-failure-queue", required=True)
    parser.add_argument("--modelica-failure-pack-planner", required=True)
    parser.add_argument("--large-model-campaign-board", default=None)
    parser.add_argument("--out", default="artifacts/dataset_failure_supply_plan/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    queue = _load_json(args.large_model_failure_queue)
    pack = _load_json(args.modelica_failure_pack_planner)
    board = _load_json(args.large_model_campaign_board)

    reasons: list[str] = []
    if not queue:
        reasons.append("large_model_queue_missing")
    if not pack:
        reasons.append("modelica_pack_plan_missing")

    large_target = _to_int(pack.get("large_target_new_cases", 0))
    medium_target = _to_int(pack.get("medium_target_new_cases", 0))
    queue_items = _to_int(queue.get("total_queue_items", 0))
    target_gap_pressure = _to_float(board.get("target_gap_pressure_index", 0.0))
    target_gap_score = _to_float(board.get("model_asset_target_gap_score", 0.0))

    phase = str(board.get("campaign_phase") or "scale_out")
    weekly_multiplier = 1
    if phase == "accelerate":
        weekly_multiplier = 2
    elif phase == "stabilize":
        weekly_multiplier = 1

    if target_gap_score >= 35.0:
        weekly_multiplier += 1
    if target_gap_pressure < 60.0:
        weekly_multiplier += 1

    weekly_supply_target = max(4, (large_target + medium_target) * weekly_multiplier)
    target_gap_supply_pressure_index = min(
        100,
        max(
            0,
            int(
                round(
                    (target_gap_score * 1.3)
                    + (max(0.0, 100.0 - target_gap_pressure) * 0.7)
                    + (queue_items * 1.5)
                )
            ),
        ),
    )

    channels = [
        {
            "channel": "mutation_generation",
            "target_cases": max(2, medium_target // 2),
            "source": "medium_failure_gaps",
        },
        {
            "channel": "scenario_parameter_sweep",
            "target_cases": max(2, large_target),
            "source": "large_scale_queue",
        },
        {
            "channel": "historical_regression_replay",
            "target_cases": max(1, queue_items // 2),
            "source": "priority_queue_regressions",
        },
        {
            "channel": "target_gap_case_harvest",
            "target_cases": max(1, int(round(target_gap_score / 10.0))),
            "source": "model_asset_target_gap_backlog",
        },
    ]

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif weekly_supply_target > 0:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "weekly_supply_target": weekly_supply_target,
        "large_supply_target": max(2, large_target),
        "medium_supply_target": max(2, medium_target),
        "target_gap_supply_pressure_index": target_gap_supply_pressure_index,
        "target_gap_pressure_index": round(target_gap_pressure, 2),
        "model_asset_target_gap_score": round(target_gap_score, 2),
        "channels": channels,
        "reasons": sorted(set(reasons)),
        "sources": {
            "large_model_failure_queue": args.large_model_failure_queue,
            "modelica_failure_pack_planner": args.modelica_failure_pack_planner,
            "large_model_campaign_board": args.large_model_campaign_board,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "weekly_supply_target": weekly_supply_target}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
