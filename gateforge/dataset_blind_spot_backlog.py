from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FAILURE_TYPES = [
    "numerical_divergence",
    "solver_non_convergence",
    "boundary_condition_drift",
    "unit_parameter_mismatch",
    "stability_regression",
]
REQUIRED_MODEL_SCALES = ["small", "medium", "large"]
REQUIRED_STAGES = ["compile", "initialization", "simulation", "postprocess"]


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


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _to_list_str(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if isinstance(v, str)]


def _priority(score: int) -> str:
    if score >= 8:
        return "P0"
    if score >= 5:
        return "P1"
    if score >= 3:
        return "P2"
    return "P3"


def _task(task_id: str, title: str, reason: str, score: int, evidence: dict) -> dict:
    return {
        "task_id": task_id,
        "title": title,
        "reason": reason,
        "impact_score": score,
        "priority": _priority(score),
        "evidence": evidence,
        "status": "OPEN",
    }


def _build_tasks(taxonomy: dict, distribution: dict, registry: dict, snapshot: dict) -> list[dict]:
    tasks: list[dict] = []

    missing_failure_types = _to_list_str(taxonomy.get("missing_failure_types"))
    for ft in missing_failure_types:
        tasks.append(
            _task(
                f"blindspot.failure_type.{ft}",
                f"Add failure type coverage: {ft}",
                "taxonomy_missing_failure_type",
                6,
                {"failure_type": ft},
            )
        )

    missing_model_scales = _to_list_str(taxonomy.get("missing_model_scales"))
    for scale in missing_model_scales:
        score = 7 if scale == "large" else 5
        tasks.append(
            _task(
                f"blindspot.model_scale.{scale}",
                f"Expand model scale coverage: {scale}",
                "taxonomy_missing_model_scale",
                score,
                {"model_scale": scale},
            )
        )

    missing_stages = _to_list_str(taxonomy.get("missing_stages"))
    for stage in missing_stages:
        tasks.append(
            _task(
                f"blindspot.stage.{stage}",
                f"Add failure stage evidence: {stage}",
                "taxonomy_missing_stage",
                4,
                {"failure_stage": stage},
            )
        )

    drift_score = float(distribution.get("distribution_drift_score", 0.0) or 0.0)
    if drift_score > 0.35:
        tasks.append(
            _task(
                "blindspot.distribution_drift",
                "Rebalance failure distribution benchmark",
                "distribution_drift_exceeds_threshold",
                7,
                {"distribution_drift_score": round(drift_score, 4)},
            )
        )

    fp_rate = float(distribution.get("false_positive_rate_after", 0.0) or 0.0)
    if fp_rate > 0.08:
        tasks.append(
            _task(
                "blindspot.false_positive_rate",
                "Reduce false positive rate in benchmark",
                "false_positive_rate_high",
                6,
                {"false_positive_rate_after": round(fp_rate, 4)},
            )
        )

    regression_rate = float(distribution.get("regression_rate_after", 0.0) or 0.0)
    if regression_rate > 0.15:
        tasks.append(
            _task(
                "blindspot.regression_rate",
                "Mitigate regression-prone failure classes",
                "regression_rate_high",
                8,
                {"regression_rate_after": round(regression_rate, 4)},
            )
        )

    registry_missing_scales = _to_list_str(registry.get("missing_model_scales"))
    for scale in registry_missing_scales:
        tasks.append(
            _task(
                f"blindspot.registry.model_scale.{scale}",
                f"Register corpus cases for model scale: {scale}",
                "registry_missing_model_scale",
                5 if scale != "large" else 7,
                {"model_scale": scale},
            )
        )

    if _to_int(registry.get("duplicate_fingerprint_count", 0)) > 0:
        tasks.append(
            _task(
                "blindspot.registry.dedup",
                "Resolve duplicate failure fingerprints",
                "registry_duplicate_fingerprint_detected",
                4,
                {"duplicate_fingerprint_count": _to_int(registry.get("duplicate_fingerprint_count", 0))},
            )
        )

    snapshot_risks = _to_list_str(snapshot.get("risks"))
    for risk in snapshot_risks:
        if risk.startswith("dataset_failure_") or risk.startswith("dataset_model_scale_"):
            tasks.append(
                _task(
                    f"blindspot.snapshot.{risk}",
                    f"Address governance risk: {risk}",
                    "snapshot_risk_present",
                    3,
                    {"risk": risk},
                )
            )

    dedup: dict[str, dict] = {}
    for row in tasks:
        task_id = str(row.get("task_id") or "")
        if not task_id:
            continue
        existing = dedup.get(task_id)
        if not existing or int(row.get("impact_score") or 0) > int(existing.get("impact_score") or 0):
            dedup[task_id] = row

    final = sorted(
        dedup.values(),
        key=lambda x: (-int(x.get("impact_score") or 0), str(x.get("task_id") or "")),
    )
    return final


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Blind Spot Backlog",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_open_tasks: `{payload.get('total_open_tasks')}`",
        f"- p0_count: `{payload.get('priority_counts', {}).get('P0', 0)}`",
        f"- p1_count: `{payload.get('priority_counts', {}).get('P1', 0)}`",
        "",
        "## Top Tasks",
        "",
    ]
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    if tasks:
        for row in tasks[:15]:
            lines.append(
                f"- `{row.get('priority')}` `{row.get('task_id')}` score=`{row.get('impact_score')}` reason=`{row.get('reason')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate blind-spot backlog from governance evidence signals")
    parser.add_argument("--failure-taxonomy-coverage", default=None)
    parser.add_argument("--failure-distribution-benchmark", default=None)
    parser.add_argument("--failure-corpus-registry-summary", default=None)
    parser.add_argument("--snapshot-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_blind_spot_backlog/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    taxonomy = _load_json(args.failure_taxonomy_coverage)
    distribution = _load_json(args.failure_distribution_benchmark)
    registry = _load_json(args.failure_corpus_registry_summary)
    snapshot = _load_json(args.snapshot_summary)

    tasks = _build_tasks(taxonomy, distribution, registry, snapshot)
    priority_counts = {
        "P0": len([x for x in tasks if x.get("priority") == "P0"]),
        "P1": len([x for x in tasks if x.get("priority") == "P1"]),
        "P2": len([x for x in tasks if x.get("priority") == "P2"]),
        "P3": len([x for x in tasks if x.get("priority") == "P3"]),
    }

    status = "PASS" if not tasks else "NEEDS_REVIEW"
    if not any([taxonomy, distribution, registry, snapshot]):
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_open_tasks": len(tasks),
        "priority_counts": priority_counts,
        "tasks": tasks,
        "sources": {
            "failure_taxonomy_coverage": args.failure_taxonomy_coverage,
            "failure_distribution_benchmark": args.failure_distribution_benchmark,
            "failure_corpus_registry_summary": args.failure_corpus_registry_summary,
            "snapshot_summary": args.snapshot_summary,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "total_open_tasks": payload.get("total_open_tasks")}))
    if payload.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
