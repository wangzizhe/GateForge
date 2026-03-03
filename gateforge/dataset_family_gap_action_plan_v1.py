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


def _write_json(path: str, payload: object) -> None:
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
        "# GateForge Family Gap Action Plan v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_actions: `{payload.get('total_actions')}`",
        f"- p0_actions: `{payload.get('p0_actions')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create family-coverage gap actions from family board + milestone checkpoint")
    parser.add_argument("--real-model-family-coverage-board-summary", required=True)
    parser.add_argument("--weekly-scale-milestone-checkpoint-summary", default=None)
    parser.add_argument("--min-models-per-family", type=int, default=3)
    parser.add_argument("--out", default="artifacts/dataset_family_gap_action_plan_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    family_board = _load_json(args.real_model_family_coverage_board_summary)
    checkpoint = _load_json(args.weekly_scale_milestone_checkpoint_summary)
    reasons: list[str] = []
    if not family_board:
        reasons.append("real_model_family_coverage_board_summary_missing")

    families = family_board.get("families") if isinstance(family_board.get("families"), list) else []
    min_models = max(1, int(args.min_models_per_family))
    milestone_grade = str(checkpoint.get("milestone_grade") or "C")

    actions: list[dict] = []
    for row in families:
        if not isinstance(row, dict):
            continue
        family = str(row.get("family") or "unknown")
        model_count = _to_int(row.get("model_count", 0))
        large_ratio = _to_float(row.get("large_ratio", 0.0))
        shortfall = max(0, min_models - model_count)
        if shortfall <= 0 and large_ratio >= 0.2:
            continue
        priority = "P1"
        if shortfall >= 2 or (large_ratio < 0.1 and model_count > 0):
            priority = "P0"
        if milestone_grade in {"C", "D"} and priority == "P1":
            priority = "P0"
        actions.append(
            {
                "action_id": f"family_gap.{family}",
                "priority": priority,
                "family": family,
                "current_model_count": model_count,
                "current_large_ratio": round(large_ratio, 4),
                "target_model_count": min_models,
                "target_large_ratio": 0.2,
                "model_shortfall": shortfall,
                "reason": "family_coverage_gap",
            }
        )

    actions.sort(key=lambda a: (str(a.get("priority") or "P9"), -_to_int(a.get("model_shortfall", 0)), str(a.get("family") or "")))
    alerts: list[str] = []
    if actions:
        alerts.append("family_gap_actions_generated")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif actions:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_actions": len(actions),
        "p0_actions": len([a for a in actions if str(a.get("priority") or "") == "P0"]),
        "actions": actions,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_family_coverage_board_summary": args.real_model_family_coverage_board_summary,
            "weekly_scale_milestone_checkpoint_summary": args.weekly_scale_milestone_checkpoint_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_actions": len(actions), "p0_actions": payload["p0_actions"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
