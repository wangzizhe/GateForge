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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _status(v: object) -> str:
    return str(v or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Moat Execution Cadence v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- execution_cadence_score: `{payload.get('execution_cadence_score')}`",
        f"- weekly_model_target: `{payload.get('weekly_model_target')}`",
        f"- weekly_mutation_target: `{payload.get('weekly_mutation_target')}`",
        f"- campaign_completion_ratio_pct: `{payload.get('campaign_completion_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build moat execution cadence score from weekly execution signals")
    parser.add_argument("--moat-hard-evidence-plan-summary", required=True)
    parser.add_argument("--mutation-depth-pressure-board-summary", required=True)
    parser.add_argument("--real-model-supply-pipeline-summary", required=True)
    parser.add_argument("--mutation-campaign-tracker-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_moat_execution_cadence_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    plan = _load_json(args.moat_hard_evidence_plan_summary)
    depth = _load_json(args.mutation_depth_pressure_board_summary)
    supply = _load_json(args.real_model_supply_pipeline_summary)
    campaign = _load_json(args.mutation_campaign_tracker_summary)

    reasons: list[str] = []
    if not plan:
        reasons.append("moat_hard_evidence_plan_summary_missing")
    if not depth:
        reasons.append("mutation_depth_pressure_board_summary_missing")
    if not supply:
        reasons.append("real_model_supply_pipeline_summary_missing")
    if not campaign:
        reasons.append("mutation_campaign_tracker_summary_missing")

    execution_focus = _to_float(plan.get("execution_focus_score", 0.0))
    model_velocity = _to_float(supply.get("growth_velocity_score", 0.0))
    pipeline_score = _to_float(supply.get("supply_pipeline_score", 0.0))
    mutation_pressure = _to_float(depth.get("mutation_depth_pressure_index", 100.0))
    weekly_mutation_target = _to_int(depth.get("recommended_weekly_mutation_target", 0))
    campaign_ratio = _to_float(campaign.get("completion_ratio_pct", 0.0))

    weekly_model_target = max(1, min(8, int(round(max(0.0, 100.0 - mutation_pressure) / 20.0 + model_velocity / 35.0))))

    execution_cadence_score = round(
        max(
            0.0,
            min(
                100.0,
                execution_focus * 0.30
                + model_velocity * 0.20
                + pipeline_score * 0.20
                + campaign_ratio * 0.20
                + max(0.0, 100.0 - mutation_pressure) * 0.10,
            ),
        ),
        2,
    )

    alerts: list[str] = []
    if _status(plan.get("status")) != "PASS":
        alerts.append("hard_evidence_plan_not_pass")
    if _status(supply.get("status")) != "PASS":
        alerts.append("real_model_supply_pipeline_not_pass")
    if mutation_pressure > 35.0:
        alerts.append("mutation_depth_pressure_high")
    if campaign_ratio < 65.0:
        alerts.append("mutation_campaign_completion_low")
    if execution_cadence_score < 72.0:
        alerts.append("execution_cadence_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "execution_cadence_score": execution_cadence_score,
        "weekly_model_target": weekly_model_target,
        "weekly_mutation_target": weekly_mutation_target,
        "campaign_completion_ratio_pct": campaign_ratio,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "execution_focus_score": execution_focus,
            "growth_velocity_score": model_velocity,
            "supply_pipeline_score": pipeline_score,
            "mutation_depth_pressure_index": mutation_pressure,
            "mutation_campaign_completion_ratio_pct": campaign_ratio,
        },
        "sources": {
            "moat_hard_evidence_plan_summary": args.moat_hard_evidence_plan_summary,
            "mutation_depth_pressure_board_summary": args.mutation_depth_pressure_board_summary,
            "real_model_supply_pipeline_summary": args.real_model_supply_pipeline_summary,
            "mutation_campaign_tracker_summary": args.mutation_campaign_tracker_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "execution_cadence_score": execution_cadence_score, "weekly_model_target": weekly_model_target}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
