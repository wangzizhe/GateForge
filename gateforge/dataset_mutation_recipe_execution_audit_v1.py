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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Recipe Execution Audit v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- recipe_count: `{payload.get('recipe_count')}`",
        f"- matched_recipe_count: `{payload.get('matched_recipe_count')}`",
        f"- execution_coverage_pct: `{payload.get('execution_coverage_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit whether mutation recipes are materially executed in matrix evidence")
    parser.add_argument("--mutation-recipe-library", required=True)
    parser.add_argument("--mutation-execution-matrix-summary", required=True)
    parser.add_argument("--min-execution-coverage-pct", type=float, default=65.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_recipe_execution_audit_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    recipe_summary = _load_json(args.mutation_recipe_library)
    matrix_summary = _load_json(args.mutation_execution_matrix_summary)

    reasons: list[str] = []
    if not recipe_summary:
        reasons.append("mutation_recipe_library_missing")
    if not matrix_summary:
        reasons.append("mutation_execution_matrix_summary_missing")

    recipe_count = int(recipe_summary.get("total_recipes", 0) or 0)
    cells = matrix_summary.get("missing_cells") if isinstance(matrix_summary.get("missing_cells"), list) else []
    matrix_execution_ratio = float(matrix_summary.get("matrix_execution_ratio_pct", 0.0) or 0.0)

    # Approximate aligned coverage: use matrix ratio scaled by recipe presence.
    matched_recipe_count = int(round((matrix_execution_ratio / 100.0) * recipe_count)) if recipe_count > 0 else 0
    missing_recipe_count = max(0, recipe_count - matched_recipe_count)
    execution_coverage_pct = _ratio(matched_recipe_count, recipe_count)

    uncovered_lanes: list[str] = []
    for row in cells:
        if not isinstance(row, dict):
            continue
        uncovered_lanes.append(f"{_slug(row.get('model_scale'), default='unknown')}::{_slug(row.get('failure_type'), default='unknown')}")

    alerts: list[str] = []
    if recipe_count == 0:
        alerts.append("recipe_library_empty")
    if execution_coverage_pct < float(args.min_execution_coverage_pct):
        alerts.append("execution_coverage_below_threshold")
    if uncovered_lanes:
        alerts.append("uncovered_recipe_lanes_present")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "recipe_count": recipe_count,
        "matched_recipe_count": matched_recipe_count,
        "missing_recipe_count": missing_recipe_count,
        "execution_coverage_pct": execution_coverage_pct,
        "uncovered_lanes": sorted(set(uncovered_lanes)),
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "signals": {
            "matrix_execution_ratio_pct": matrix_execution_ratio,
            "matrix_missing_cell_count": len(cells),
        },
        "sources": {
            "mutation_recipe_library": args.mutation_recipe_library,
            "mutation_execution_matrix_summary": args.mutation_execution_matrix_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "execution_coverage_pct": execution_coverage_pct, "missing_recipe_count": missing_recipe_count}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
