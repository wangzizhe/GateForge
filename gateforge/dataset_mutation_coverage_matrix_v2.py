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


def _slug(v: object, *, default: str = "unknown") -> str:
    s = str(v or "").strip().lower()
    if not s:
        return default
    return s.replace("-", "_").replace(" ", "_")


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _extract_model_scale_map(registry: dict) -> dict[str, str]:
    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "").strip()
        if not model_id:
            continue
        out[model_id] = _slug(row.get("suggested_scale") or row.get("target_scale"), default="unknown")
    return out


def _extract_observed_failures(observations: dict) -> dict[str, set[str]]:
    rows = observations.get("observations") if isinstance(observations.get("observations"), list) else []
    out: dict[str, set[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        labels: set[str] = set()
        many = row.get("observed_failure_types") if isinstance(row.get("observed_failure_types"), list) else []
        for item in many:
            if isinstance(item, str) and item.strip():
                labels.add(_slug(item))
        one = str(row.get("observed_failure_type") or "").strip()
        if one:
            labels.add(_slug(one))
        out[mutation_id] = labels
    return out


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Coverage Matrix v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- matrix_coverage_score: `{payload.get('matrix_coverage_score')}`",
        f"- total_matrix_cells: `{payload.get('total_matrix_cells')}`",
        f"- covered_matrix_cells: `{payload.get('covered_matrix_cells')}`",
        f"- high_risk_uncovered_cells: `{payload.get('high_risk_uncovered_cells')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build scale x failure x mutation-method coverage matrix and gap plan")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--replay-observations", required=True)
    parser.add_argument("--min-matrix-coverage-score", type=float, default=82.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_coverage_matrix_v2/summary.json")
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

    model_scale = _extract_model_scale_map(registry)
    observed = _extract_observed_failures(observations)

    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    cells: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        method = _slug(row.get("mutation_type") or row.get("mutator") or row.get("method"), default="unknown")
        expected_failure = _slug(row.get("expected_failure_type"), default="unknown")
        model_id = str(row.get("target_model_id") or row.get("model_id") or row.get("source_model_id") or "").strip()
        scale = model_scale.get(model_id, _slug(row.get("target_scale"), default="unknown"))
        key = (scale, expected_failure, method)
        bucket = cells.setdefault(key, {"planned": 0, "covered": 0, "mutation_ids": []})
        bucket["planned"] = int(bucket.get("planned", 0)) + 1
        mids = bucket.get("mutation_ids") if isinstance(bucket.get("mutation_ids"), list) else []
        if mutation_id:
            mids.append(mutation_id)
        bucket["mutation_ids"] = mids
        if mutation_id and expected_failure in observed.get(mutation_id, set()):
            bucket["covered"] = int(bucket.get("covered", 0)) + 1

    high_risk_failures = {"solver_non_convergence", "semantic_regression", "simulate_error", "runtime_overflow"}
    total_matrix_cells = len(cells)
    covered_matrix_cells = 0
    uncovered: list[dict] = []
    high_risk_uncovered: list[dict] = []

    for (scale, failure_type, method), bucket in sorted(cells.items()):
        planned = _to_int(bucket.get("planned", 0))
        covered = _to_int(bucket.get("covered", 0))
        missing = max(0, planned - covered)
        if planned > 0 and missing == 0:
            covered_matrix_cells += 1
            continue
        entry = {
            "model_scale": scale,
            "failure_type": failure_type,
            "mutation_method": method,
            "planned": planned,
            "covered": covered,
            "missing": missing,
        }
        uncovered.append(entry)
        if scale in {"medium", "large"} and failure_type in high_risk_failures:
            high_risk_uncovered.append(entry)

    coverage_ratio = 0.0 if total_matrix_cells == 0 else (covered_matrix_cells / total_matrix_cells) * 100.0
    matrix_coverage_score = round(
        max(0.0, min(100.0, coverage_ratio - min(24.0, len(high_risk_uncovered) * 4.0))),
        2,
    )

    top_gap_plan = sorted(
        uncovered,
        key=lambda x: (
            -1 if x.get("model_scale") == "large" else 0,
            -1 if x.get("failure_type") in high_risk_failures else 0,
            -_to_int(x.get("missing", 0)),
            str(x.get("mutation_method") or ""),
        ),
    )[:10]

    alerts: list[str] = []
    if total_matrix_cells == 0:
        alerts.append("matrix_cells_empty")
    if uncovered:
        alerts.append("matrix_uncovered_cells_present")
    if high_risk_uncovered:
        alerts.append("matrix_high_risk_uncovered_cells_present")
    if matrix_coverage_score < float(args.min_matrix_coverage_score):
        alerts.append("matrix_coverage_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "matrix_coverage_score": matrix_coverage_score,
        "total_matrix_cells": total_matrix_cells,
        "covered_matrix_cells": covered_matrix_cells,
        "uncovered_matrix_cells": len(uncovered),
        "high_risk_uncovered_cells": len(high_risk_uncovered),
        "top_10_gap_plan": top_gap_plan,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_registry": args.real_model_registry,
            "validated_mutation_manifest": args.validated_mutation_manifest,
            "replay_observations": args.replay_observations,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "matrix_coverage_score": matrix_coverage_score,
                "high_risk_uncovered_cells": len(high_risk_uncovered),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
