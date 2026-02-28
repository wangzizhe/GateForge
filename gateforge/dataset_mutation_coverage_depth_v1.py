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


def _extract_models(registry: dict) -> dict[str, str]:
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


def _extract_observed_counts(observations: dict) -> dict[str, int]:
    rows = observations.get("observations") if isinstance(observations.get("observations"), list) else []
    out: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        labels = row.get("observed_failure_types")
        if isinstance(labels, list):
            out[mutation_id] = len([x for x in labels if isinstance(x, str) and str(x).strip()])
        elif str(row.get("observed_failure_type") or "").strip():
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
        "# GateForge Mutation Coverage Depth v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- coverage_depth_score: `{payload.get('coverage_depth_score')}`",
        f"- total_cells: `{payload.get('total_cells')}`",
        f"- covered_cells: `{payload.get('covered_cells')}`",
        f"- uncovered_cells_count: `{payload.get('uncovered_cells_count')}`",
        f"- high_risk_gaps_count: `{payload.get('high_risk_gaps_count')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build mutation coverage depth over scale x failure_type x stage")
    parser.add_argument("--real-model-registry", required=True)
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--replay-observations", required=True)
    parser.add_argument("--min-evidence-runs", type=int, default=2)
    parser.add_argument("--min-coverage-depth-score", type=float, default=85.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_coverage_depth_v1/summary.json")
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

    model_scale_by_id = _extract_models(registry)
    obs_counts = _extract_observed_counts(observations)
    mutations = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []

    min_runs = max(1, int(args.min_evidence_runs))

    cells: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in mutations:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        model_id = str(row.get("target_model_id") or row.get("model_id") or row.get("source_model_id") or "").strip()
        scale = model_scale_by_id.get(model_id, _slug(row.get("target_scale"), default="unknown"))
        failure_type = _slug(row.get("expected_failure_type"), default="unknown")
        stage = _slug(row.get("expected_stage") or row.get("stage"), default="simulate")
        key = (scale, failure_type, stage)
        bucket = cells.setdefault(key, {"planned": 0, "covered": 0})
        bucket["planned"] += 1
        if mutation_id and int(obs_counts.get(mutation_id, 0)) >= min_runs:
            bucket["covered"] += 1

    total_cells = len(cells)
    covered_cells = 0
    uncovered_cells: list[dict] = []
    high_risk_gaps: list[dict] = []
    critical_failure_types = {
        "simulate_error",
        "semantic_regression",
        "solver_non_convergence",
        "runtime_overflow",
    }

    for (scale, failure_type, stage), v in sorted(cells.items()):
        planned = int(v.get("planned", 0))
        covered = int(v.get("covered", 0))
        if covered >= planned and planned > 0:
            covered_cells += 1
        else:
            gap = {
                "model_scale": scale,
                "failure_type": failure_type,
                "stage": stage,
                "planned_mutations": planned,
                "covered_mutations": covered,
                "missing_mutations": max(0, planned - covered),
            }
            uncovered_cells.append(gap)
            if scale in {"large", "medium"} and failure_type in critical_failure_types:
                high_risk_gaps.append(gap)

    coverage_pct = _ratio(covered_cells, total_cells)
    coverage_depth_score = round(max(0.0, min(100.0, coverage_pct - min(20.0, len(high_risk_gaps) * 4.0))), 2)

    alerts: list[str] = []
    if total_cells == 0:
        alerts.append("coverage_cells_empty")
    if uncovered_cells:
        alerts.append("uncovered_cells_present")
    if high_risk_gaps:
        alerts.append("high_risk_gaps_present")
    if coverage_depth_score < float(args.min_coverage_depth_score):
        alerts.append("coverage_depth_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "coverage_depth_score": coverage_depth_score,
        "total_cells": total_cells,
        "covered_cells": covered_cells,
        "uncovered_cells_count": len(uncovered_cells),
        "high_risk_gaps_count": len(high_risk_gaps),
        "uncovered_cells": uncovered_cells,
        "high_risk_gaps": high_risk_gaps,
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
                "coverage_depth_score": coverage_depth_score,
                "uncovered_cells_count": len(uncovered_cells),
                "high_risk_gaps_count": len(high_risk_gaps),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
