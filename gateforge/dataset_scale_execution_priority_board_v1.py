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
        "# GateForge Scale Execution Priority Board v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- task_count: `{payload.get('task_count')}`",
        f"- p0_tasks: `{payload.get('p0_tasks')}`",
        f"- projected_weeks_to_close_key_gaps: `{payload.get('projected_weeks_to_close_key_gaps')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate priority execution board from scale target gaps and gate signals")
    parser.add_argument("--scale-target-gap-summary", required=True)
    parser.add_argument("--ingest-source-channel-planner-summary", default=None)
    parser.add_argument("--hard-moat-gates-summary", default=None)
    parser.add_argument("--coverage-backfill-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_scale_execution_priority_board_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    gap = _load_json(args.scale_target_gap_summary)
    planner = _load_json(args.ingest_source_channel_planner_summary)
    hard_moat = _load_json(args.hard_moat_gates_summary)
    backfill = _load_json(args.coverage_backfill_summary)

    reasons: list[str] = []
    if not gap:
        reasons.append("scale_target_gap_summary_missing")

    tasks: list[dict] = []
    gap_models = _to_int(gap.get("gap_models", 0))
    gap_mutations = _to_int(gap.get("gap_reproducible_mutations", 0))
    gap_hardness = _to_float(gap.get("gap_hardness_score", 0.0))
    required_models_weekly = _to_int(gap.get("required_weekly_new_models", 0))
    required_mutations_weekly = _to_int(gap.get("required_weekly_new_reproducible_mutations", 0))
    planner_p0 = _to_int(planner.get("p0_channels", 0))
    backfill_p0 = _to_int(backfill.get("p0_tasks", 0))
    hard_failed = _to_int(hard_moat.get("failed_gate_count", 0))

    if gap_models > 0:
        tasks.append(
            {
                "task_id": "scale.expand_real_model_pool",
                "priority": "P0" if required_models_weekly >= 10 else "P1",
                "lane": "intake",
                "target": f"+{required_models_weekly}/week models",
                "reason": "model_pool_gap_open",
            }
        )
    if gap_mutations > 0:
        tasks.append(
            {
                "task_id": "scale.expand_reproducible_mutations",
                "priority": "P0" if required_mutations_weekly >= 100 else "P1",
                "lane": "mutation",
                "target": f"+{required_mutations_weekly}/week reproducible_mutations",
                "reason": "reproducible_mutation_gap_open",
            }
        )
    if gap_hardness > 0:
        tasks.append(
            {
                "task_id": "scale.raise_hardness_score",
                "priority": "P1",
                "lane": "quality",
                "target": f"+{round(gap_hardness, 2)} hardness_score",
                "reason": "hardness_gap_open",
            }
        )
    if planner_p0 > 0:
        tasks.append(
            {
                "task_id": "scale.close_ingest_p0_channels",
                "priority": "P0",
                "lane": "intake",
                "target": f"close_{planner_p0}_p0_channels",
                "reason": "ingest_channel_pressure",
            }
        )
    if backfill_p0 > 0:
        tasks.append(
            {
                "task_id": "scale.close_backfill_p0_tasks",
                "priority": "P0",
                "lane": "mutation",
                "target": f"close_{backfill_p0}_p0_backfill_tasks",
                "reason": "coverage_backfill_pressure",
            }
        )
    if hard_failed > 0:
        tasks.append(
            {
                "task_id": "scale.fix_hard_moat_failed_gates",
                "priority": "P0",
                "lane": "governance",
                "target": f"fix_{hard_failed}_failed_gates",
                "reason": "hard_moat_gates_not_green",
            }
        )

    tasks.sort(key=lambda x: (str(x.get("priority") or "P9"), str(x.get("lane") or ""), str(x.get("task_id") or "")))
    p0_tasks = len([t for t in tasks if str(t.get("priority") or "") == "P0"])

    projected_weeks = 0
    if required_models_weekly > 0:
        projected_weeks = max(projected_weeks, 1)
    if required_mutations_weekly > 0:
        projected_weeks = max(projected_weeks, 2 if required_mutations_weekly >= 100 else 1)
    if p0_tasks >= 4:
        projected_weeks = max(projected_weeks, 3)
    elif p0_tasks >= 2:
        projected_weeks = max(projected_weeks, 2)

    alerts: list[str] = []
    if p0_tasks > 0:
        alerts.append("p0_tasks_present")
    if hard_failed > 0:
        alerts.append("hard_moat_failures_present")
    if str(gap.get("status") or "") == "NEEDS_REVIEW":
        alerts.append("scale_target_gap_needs_review")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif tasks:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "task_count": len(tasks),
        "p0_tasks": p0_tasks,
        "projected_weeks_to_close_key_gaps": projected_weeks,
        "tasks": tasks,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "gap_models": gap_models,
            "gap_reproducible_mutations": gap_mutations,
            "gap_hardness_score": round(gap_hardness, 2),
            "required_weekly_new_models": required_models_weekly,
            "required_weekly_new_reproducible_mutations": required_mutations_weekly,
            "planner_p0_channels": planner_p0,
            "backfill_p0_tasks": backfill_p0,
            "hard_moat_failed_gate_count": hard_failed,
        },
        "sources": {
            "scale_target_gap_summary": args.scale_target_gap_summary,
            "ingest_source_channel_planner_summary": args.ingest_source_channel_planner_summary,
            "hard_moat_gates_summary": args.hard_moat_gates_summary,
            "coverage_backfill_summary": args.coverage_backfill_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "task_count": len(tasks), "p0_tasks": p0_tasks}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
