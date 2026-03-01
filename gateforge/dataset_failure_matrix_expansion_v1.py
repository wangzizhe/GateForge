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
        "# GateForge Failure Matrix Expansion v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- expansion_readiness_score: `{payload.get('expansion_readiness_score')}`",
        f"- high_risk_uncovered_cells: `{payload.get('high_risk_uncovered_cells')}`",
        f"- planned_expansion_tasks: `{payload.get('planned_expansion_tasks')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build expansion plan from mutation coverage matrix gaps")
    parser.add_argument("--mutation-coverage-matrix-summary", required=True)
    parser.add_argument("--target-high-risk-uncovered-cells", type=int, default=0)
    parser.add_argument("--out", default="artifacts/dataset_failure_matrix_expansion_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    matrix = _load_json(args.mutation_coverage_matrix_summary)
    reasons: list[str] = []
    if not matrix:
        reasons.append("mutation_coverage_matrix_summary_missing")

    high_risk_uncovered = _to_int(matrix.get("high_risk_uncovered_cells", 0))
    matrix_score = _to_float(matrix.get("matrix_coverage_score", 0.0))
    gap_plan = matrix.get("top_10_gap_plan") if isinstance(matrix.get("top_10_gap_plan"), list) else []

    expansion_tasks: list[dict] = []
    for idx, row in enumerate(gap_plan[:10], start=1):
        if not isinstance(row, dict):
            continue
        expansion_tasks.append(
            {
                "task_id": f"expand_{idx:02d}",
                "model_scale": row.get("model_scale"),
                "failure_type": row.get("failure_type"),
                "mutation_method": row.get("mutation_method"),
                "missing": row.get("missing"),
            }
        )

    readiness = 55.0
    readiness += min(20.0, matrix_score * 0.2)
    readiness -= min(25.0, high_risk_uncovered * 4.0)
    readiness += min(15.0, len(expansion_tasks) * 1.5)
    readiness = round(max(0.0, min(100.0, readiness)), 2)

    alerts: list[str] = []
    if high_risk_uncovered > int(args.target_high_risk_uncovered_cells):
        alerts.append("high_risk_uncovered_cells_above_target")
    if len(expansion_tasks) == 0:
        alerts.append("no_expansion_tasks_generated")
    if readiness < 70.0:
        alerts.append("expansion_readiness_score_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "expansion_readiness_score": readiness,
        "matrix_coverage_score": matrix_score,
        "high_risk_uncovered_cells": high_risk_uncovered,
        "planned_expansion_tasks": len(expansion_tasks),
        "expansion_tasks": expansion_tasks,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {"mutation_coverage_matrix_summary": args.mutation_coverage_matrix_summary},
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "expansion_readiness_score": readiness, "planned_expansion_tasks": len(expansion_tasks)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
