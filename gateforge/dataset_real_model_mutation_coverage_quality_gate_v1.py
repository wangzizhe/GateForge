from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_FAILURE_TYPES = [
    "simulate_error",
    "model_check_error",
    "semantic_regression",
    "numerical_instability",
    "constraint_violation",
]


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


def _slug(v: object, *, default: str = "") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Mutation Coverage Quality Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- matrix_cell_count: `{payload.get('matrix_cell_count')}`",
        f"- covered_required_cell_count: `{payload.get('covered_required_cell_count')}`",
        f"- required_cell_count: `{payload.get('required_cell_count')}`",
        f"- required_cell_coverage_ratio_pct: `{payload.get('required_cell_coverage_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate mutation execution quality on scale x failure-type execution coverage")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--required-scales", default="medium,large")
    parser.add_argument("--required-failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--min-cell-execution-ratio-pct", type=float, default=95.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_mutation_coverage_quality_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.real_model_registry)
    manifest = _load_json(args.validated_mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)

    reasons: list[str] = []
    if not registry:
        reasons.append("real_model_registry_missing")
    if not manifest:
        reasons.append("validated_mutation_manifest_missing")
    if not raw:
        reasons.append("mutation_raw_observations_missing")

    required_scales = {_slug(x, default="") for x in str(args.required_scales).split(",") if _slug(x, default="")}
    required_failure_types = {
        _slug(x, default="") for x in str(args.required_failure_types).split(",") if _slug(x, default="")
    }

    model_scale: dict[str, str] = {}
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "").strip()
        if not model_id:
            continue
        model_scale[model_id] = _slug(row.get("suggested_scale") or row.get("target_scale"), default="unknown")

    executed_mutation_ids: set[str] = set()
    obs_rows = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    for row in obs_rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        if str(row.get("execution_status") or "").strip().upper() == "EXECUTED":
            executed_mutation_ids.add(mutation_id)

    planned_cells: dict[tuple[str, str], dict[str, int]] = {}
    manifest_rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    for row in manifest_rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        model_id = str(row.get("target_model_id") or row.get("model_id") or "").strip()
        scale = model_scale.get(model_id, _slug(row.get("target_scale"), default="unknown"))
        failure_type = _slug(row.get("expected_failure_type"), default="unknown")
        key = (scale, failure_type)
        bucket = planned_cells.setdefault(key, {"planned": 0, "executed": 0})
        bucket["planned"] += 1
        if mutation_id in executed_mutation_ids:
            bucket["executed"] += 1

    required_cells = {(s, f) for s in required_scales for f in required_failure_types}
    matrix_cells: list[dict] = []
    covered_required = 0
    low_required_cells: list[dict] = []
    missing_required_cells: list[dict] = []

    for key in sorted(required_cells):
        scale, failure_type = key
        bucket = planned_cells.get(key, {"planned": 0, "executed": 0})
        planned = _to_int(bucket.get("planned", 0))
        executed = _to_int(bucket.get("executed", 0))
        ratio = _ratio(executed, planned)
        cell = {
            "model_scale": scale,
            "failure_type": failure_type,
            "planned_mutations": planned,
            "executed_mutations": executed,
            "execution_ratio_pct": ratio,
        }
        matrix_cells.append(cell)
        if planned == 0:
            missing_required_cells.append(cell)
            continue
        if ratio < float(args.min_cell_execution_ratio_pct):
            low_required_cells.append(cell)
            continue
        covered_required += 1

    for (scale, failure_type), bucket in sorted(planned_cells.items()):
        if (scale, failure_type) in required_cells:
            continue
        planned = _to_int(bucket.get("planned", 0))
        executed = _to_int(bucket.get("executed", 0))
        matrix_cells.append(
            {
                "model_scale": scale,
                "failure_type": failure_type,
                "planned_mutations": planned,
                "executed_mutations": executed,
                "execution_ratio_pct": _ratio(executed, planned),
            }
        )

    required_cell_count = len(required_cells)
    required_cell_coverage_ratio_pct = _ratio(covered_required, required_cell_count)

    alerts: list[str] = []
    if missing_required_cells:
        alerts.append("required_cells_missing")
    if low_required_cells:
        alerts.append("required_cells_execution_ratio_below_threshold")
    if required_cell_coverage_ratio_pct < 100.0:
        alerts.append("required_cell_coverage_not_full")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "required_scales": sorted(required_scales),
        "required_failure_types": sorted(required_failure_types),
        "min_cell_execution_ratio_pct": float(args.min_cell_execution_ratio_pct),
        "matrix_cell_count": len(matrix_cells),
        "required_cell_count": required_cell_count,
        "covered_required_cell_count": covered_required,
        "required_cell_coverage_ratio_pct": required_cell_coverage_ratio_pct,
        "missing_required_cells": missing_required_cells,
        "low_required_cells": low_required_cells,
        "matrix_cells": matrix_cells,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_registry": args.real_model_registry,
            "validated_mutation_manifest": args.validated_mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "required_cell_count": required_cell_count,
                "covered_required_cell_count": covered_required,
                "required_cell_coverage_ratio_pct": required_cell_coverage_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
