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
        "# GateForge Mutation Depth Pressure Board v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- mutation_depth_pressure_index: `{payload.get('mutation_depth_pressure_index')}`",
        f"- high_risk_gap_count: `{payload.get('high_risk_gap_count')}`",
        f"- missing_recipe_count: `{payload.get('missing_recipe_count')}`",
        f"- recommended_weekly_mutation_target: `{payload.get('recommended_weekly_mutation_target')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _gap_task(gap: dict, idx: int) -> dict:
    scale = str(gap.get("model_scale") or "unknown")
    failure = str(gap.get("failure_type") or "unknown")
    stage = str(gap.get("stage") or "simulate")
    missing = max(1, _to_int(gap.get("missing_mutations", 1)))
    return {
        "task_id": f"mutation_depth_gap_{idx:02d}",
        "priority": "P0" if scale == "large" else "P1",
        "model_scale": scale,
        "failure_type": failure,
        "stage": stage,
        "target_missing_reduction": missing,
        "reason": "high_risk_gap" if scale in {"large", "medium"} else "gap",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build mutation-depth pressure board and action backlog")
    parser.add_argument("--mutation-coverage-depth-summary", required=True)
    parser.add_argument("--mutation-recipe-execution-audit-summary", required=True)
    parser.add_argument("--modelica-mutation-recipe-library-summary", required=True)
    parser.add_argument("--max-pressure-index", type=float, default=35.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_depth_pressure_board_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    coverage = _load_json(args.mutation_coverage_depth_summary)
    audit = _load_json(args.mutation_recipe_execution_audit_summary)
    recipe = _load_json(args.modelica_mutation_recipe_library_summary)

    reasons: list[str] = []
    if not coverage:
        reasons.append("mutation_coverage_depth_summary_missing")
    if not audit:
        reasons.append("mutation_recipe_execution_audit_summary_missing")
    if not recipe:
        reasons.append("modelica_mutation_recipe_library_summary_missing")

    coverage_score = _to_float(coverage.get("coverage_depth_score", 0.0))
    high_risk_gap_count = _to_int(coverage.get("high_risk_gaps_count", 0))
    uncovered_cells_count = _to_int(coverage.get("uncovered_cells_count", 0))
    missing_recipe_count = _to_int(audit.get("missing_recipe_count", 0))
    execution_coverage_pct = _to_float(audit.get("execution_coverage_pct", 0.0))
    high_priority_recipes = _to_int(recipe.get("high_priority_recipes", 0))

    pressure_index = round(
        max(
            0.0,
            min(
                100.0,
                (max(0.0, 100.0 - coverage_score) * 0.45)
                + (high_risk_gap_count * 8.0)
                + (missing_recipe_count * 3.5)
                + (max(0.0, 100.0 - execution_coverage_pct) * 0.2)
                + (high_priority_recipes * 1.2),
            ),
        ),
        2,
    )

    high_risk_gaps = coverage.get("high_risk_gaps") if isinstance(coverage.get("high_risk_gaps"), list) else []
    tasks: list[dict] = []
    for idx, row in enumerate(high_risk_gaps[:8], start=1):
        if isinstance(row, dict):
            tasks.append(_gap_task(row, idx))

    if missing_recipe_count > 0:
        tasks.append(
            {
                "task_id": "mutation_recipe_gap_close",
                "priority": "P1",
                "target_missing_reduction": missing_recipe_count,
                "reason": "missing_recipe_execution",
            }
        )

    recommended_weekly_mutation_target = max(
        4,
        min(
            30,
            _to_int(round(high_risk_gap_count * 2 + uncovered_cells_count * 0.6 + missing_recipe_count * 1.2 + 3)),
        ),
    )

    alerts: list[str] = []
    if high_risk_gap_count > 0:
        alerts.append("high_risk_mutation_gaps_present")
    if missing_recipe_count > 0:
        alerts.append("missing_recipe_execution_present")
    if pressure_index > float(args.max_pressure_index):
        alerts.append("mutation_depth_pressure_above_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mutation_depth_pressure_index": pressure_index,
        "high_risk_gap_count": high_risk_gap_count,
        "uncovered_cells_count": uncovered_cells_count,
        "missing_recipe_count": missing_recipe_count,
        "execution_coverage_pct": execution_coverage_pct,
        "high_priority_recipes": high_priority_recipes,
        "recommended_weekly_mutation_target": recommended_weekly_mutation_target,
        "backlog_tasks": tasks,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_coverage_depth_summary": args.mutation_coverage_depth_summary,
            "mutation_recipe_execution_audit_summary": args.mutation_recipe_execution_audit_summary,
            "modelica_mutation_recipe_library_summary": args.modelica_mutation_recipe_library_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "mutation_depth_pressure_index": pressure_index,
                "task_count": len(tasks),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
