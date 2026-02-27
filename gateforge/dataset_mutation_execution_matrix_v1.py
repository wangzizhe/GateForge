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


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _extract_models(registry: dict) -> list[dict]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_obs_map(observations: dict) -> dict[str, int]:
    rows = observations.get("observations") if isinstance(observations.get("observations"), list) else []
    out: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "")
        if not mutation_id:
            continue
        labels = row.get("observed_failure_types")
        if isinstance(labels, list):
            out[mutation_id] = len([x for x in labels if isinstance(x, str) and str(x).strip()])
            continue
        if str(row.get("observed_failure_type") or "").strip():
            out[mutation_id] = 1
    return out


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Execution Matrix v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_models: `{payload.get('total_models')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- executed_mutations: `{payload.get('executed_mutations')}`",
        f"- matrix_cell_count: `{payload.get('matrix_cell_count')}`",
        f"- matrix_execution_ratio_pct: `{payload.get('matrix_execution_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model-scale x failure-type mutation execution matrix")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--replay-observations", required=True)
    parser.add_argument("--min-evidence-runs", type=int, default=2)
    parser.add_argument("--min-scale-execution-ratio-pct", type=float, default=60.0)
    parser.add_argument("--matrix-out", default="artifacts/dataset_mutation_execution_matrix_v1/matrix.json")
    parser.add_argument("--out", default="artifacts/dataset_mutation_execution_matrix_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.real_model_registry)
    manifest = _load_json(args.validated_mutation_manifest)
    observations = _load_json(args.replay_observations)

    reasons: list[str] = []
    if not registry:
        reasons.append("real_model_registry_missing")
    if not manifest:
        reasons.append("validated_mutation_manifest_missing")
    if not observations:
        reasons.append("replay_observations_missing")

    models = _extract_models(registry)
    mutations = _extract_mutations(manifest)
    obs_count = _extract_obs_map(observations)

    model_scale_by_id: dict[str, str] = {}
    for row in models:
        model_id = str(row.get("model_id") or "").strip()
        if not model_id:
            continue
        scale = _slug(row.get("suggested_scale") or row.get("target_scale"), default="unknown")
        model_scale_by_id[model_id] = scale

    min_runs = max(1, int(args.min_evidence_runs))

    cell_counts: dict[tuple[str, str], dict[str, int]] = {}
    for row in mutations:
        mutation_id = str(row.get("mutation_id") or "").strip()
        failure_type = _slug(row.get("expected_failure_type"), default="unknown")
        model_id = str(
            row.get("target_model_id")
            or row.get("model_id")
            or row.get("source_model_id")
            or ""
        ).strip()
        scale = model_scale_by_id.get(model_id, _slug(row.get("target_scale"), default="unknown"))

        key = (scale, failure_type)
        bucket = cell_counts.setdefault(key, {"planned": 0, "executed": 0})
        bucket["planned"] += 1
        if mutation_id and obs_count.get(mutation_id, 0) >= min_runs:
            bucket["executed"] += 1

    matrix_cells: list[dict] = []
    missing_cells: list[dict] = []
    executed_mutations = 0
    total_mutations = 0
    for (scale, failure_type), counts in sorted(cell_counts.items()):
        planned = int(counts.get("planned", 0))
        executed = int(counts.get("executed", 0))
        total_mutations += planned
        executed_mutations += executed
        ratio = _ratio(executed, planned)
        cell = {
            "model_scale": scale,
            "failure_type": failure_type,
            "planned_mutations": planned,
            "executed_mutations": executed,
            "execution_ratio_pct": ratio,
        }
        matrix_cells.append(cell)
        if executed < planned:
            missing_cells.append(
                {
                    "model_scale": scale,
                    "failure_type": failure_type,
                    "missing_mutations": planned - executed,
                }
            )

    scale_totals: dict[str, dict[str, int]] = {}
    ft_totals: dict[str, dict[str, int]] = {}
    for row in matrix_cells:
        scale = str(row.get("model_scale") or "unknown")
        ftype = str(row.get("failure_type") or "unknown")
        planned = int(row.get("planned_mutations") or 0)
        executed = int(row.get("executed_mutations") or 0)

        st = scale_totals.setdefault(scale, {"planned": 0, "executed": 0})
        st["planned"] += planned
        st["executed"] += executed

        ft = ft_totals.setdefault(ftype, {"planned": 0, "executed": 0})
        ft["planned"] += planned
        ft["executed"] += executed

    scale_execution_ratio_pct = {k: _ratio(v["executed"], v["planned"]) for k, v in sorted(scale_totals.items())}
    failure_type_execution_ratio_pct = {k: _ratio(v["executed"], v["planned"]) for k, v in sorted(ft_totals.items())}

    alerts: list[str] = []
    if not models:
        alerts.append("real_model_registry_empty")
    if not mutations:
        alerts.append("validated_mutation_manifest_empty")
    if missing_cells:
        alerts.append("matrix_has_unexecuted_cells")
    low_scales = [k for k, v in scale_execution_ratio_pct.items() if v < float(args.min_scale_execution_ratio_pct)]
    if low_scales:
        alerts.append("scale_execution_ratio_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    matrix_payload = {
        "schema_version": "mutation_execution_matrix_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cells": matrix_cells,
    }
    _write_json(args.matrix_out, matrix_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": len(models),
        "total_mutations": total_mutations,
        "executed_mutations": executed_mutations,
        "matrix_cell_count": len(matrix_cells),
        "matrix_execution_ratio_pct": _ratio(executed_mutations, total_mutations),
        "scale_execution_ratio_pct": scale_execution_ratio_pct,
        "failure_type_execution_ratio_pct": failure_type_execution_ratio_pct,
        "low_scale_execution_ratio_scales": low_scales,
        "missing_cells": missing_cells,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "matrix_path": args.matrix_out,
        "sources": {
            "real_model_registry": args.real_model_registry,
            "validated_mutation_manifest": args.validated_mutation_manifest,
            "replay_observations": args.replay_observations,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "matrix_cell_count": len(matrix_cells), "matrix_execution_ratio_pct": summary["matrix_execution_ratio_pct"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
