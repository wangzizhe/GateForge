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
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]


def _load_json(path: str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_slug(value: object, *, default: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text.replace("-", "_").replace(" ", "_")


def _normalize_failure_type(value: object) -> str:
    alias = {
        "numerical_instability": "numerical_divergence",
        "solver_timeout": "solver_non_convergence",
        "unit_mismatch": "unit_parameter_mismatch",
        "parameter_mismatch": "unit_parameter_mismatch",
        "stability_degradation": "stability_regression",
    }
    key = _to_slug(value)
    return alias.get(key, key)


def _normalize_model_scale(value: object) -> str:
    alias = {
        "s": "small",
        "m": "medium",
        "l": "large",
    }
    key = _to_slug(value)
    return alias.get(key, key)


def _normalize_stage(value: object) -> str:
    alias = {
        "build": "compile",
        "init": "initialization",
        "runtime": "simulation",
        "analysis": "postprocess",
    }
    key = _to_slug(value)
    return alias.get(key, key)


def _normalize_severity(value: object) -> str:
    alias = {
        "sev0": "critical",
        "sev1": "high",
        "sev2": "medium",
        "sev3": "low",
    }
    key = _to_slug(value, default="medium")
    return alias.get(key, key)


def _extract_cases(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        rows = payload.get("cases")
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def _empty_count_map(keys: list[str]) -> dict[str, int]:
    return {k: 0 for k in keys}


def _compute_summary(catalog_paths: list[str]) -> dict:
    failure_counts: dict[str, int] = _empty_count_map(REQUIRED_FAILURE_TYPES)
    model_scale_counts: dict[str, int] = _empty_count_map(REQUIRED_MODEL_SCALES)
    stage_counts: dict[str, int] = _empty_count_map(REQUIRED_STAGES)
    severity_counts: dict[str, int] = _empty_count_map(SEVERITY_LEVELS)
    unknown_failure_type_count = 0
    unknown_model_scale_count = 0
    unknown_stage_count = 0
    unknown_severity_count = 0

    total_cases = 0
    for path in catalog_paths:
        payload = _load_json(path)
        for row in _extract_cases(payload):
            total_cases += 1

            failure_type = _normalize_failure_type(row.get("failure_type"))
            model_scale = _normalize_model_scale(row.get("model_scale"))
            stage = _normalize_stage(row.get("failure_stage"))
            severity = _normalize_severity(row.get("severity"))

            if failure_type in failure_counts:
                failure_counts[failure_type] += 1
            else:
                unknown_failure_type_count += 1
            if model_scale in model_scale_counts:
                model_scale_counts[model_scale] += 1
            else:
                unknown_model_scale_count += 1
            if stage in stage_counts:
                stage_counts[stage] += 1
            else:
                unknown_stage_count += 1
            if severity in severity_counts:
                severity_counts[severity] += 1
            else:
                unknown_severity_count += 1

    missing_failure_types = [k for k in REQUIRED_FAILURE_TYPES if failure_counts.get(k, 0) == 0]
    missing_model_scales = [k for k in REQUIRED_MODEL_SCALES if model_scale_counts.get(k, 0) == 0]
    missing_stages = [k for k in REQUIRED_STAGES if stage_counts.get(k, 0) == 0]

    blind_spots = [f"missing_failure_type:{x}" for x in missing_failure_types]
    blind_spots.extend(f"missing_model_scale:{x}" for x in missing_model_scales)
    blind_spots.extend(f"missing_stage:{x}" for x in missing_stages)
    if unknown_failure_type_count > 0:
        blind_spots.append("unknown_failure_type_present")
    if unknown_model_scale_count > 0:
        blind_spots.append("unknown_model_scale_present")
    if unknown_stage_count > 0:
        blind_spots.append("unknown_stage_present")
    if unknown_severity_count > 0:
        blind_spots.append("unknown_severity_present")

    alerts: list[str] = []
    if total_cases == 0:
        alerts.append("failure_taxonomy_empty")
    if missing_failure_types:
        alerts.append("failure_type_coverage_incomplete")
    if missing_model_scales:
        alerts.append("model_scale_coverage_incomplete")
    if missing_stages:
        alerts.append("stage_coverage_incomplete")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
    if total_cases == 0:
        status = "FAIL"

    return {
        "status": status,
        "total_cases": total_cases,
        "catalog_count": len(catalog_paths),
        "failure_type_counts": failure_counts,
        "model_scale_counts": model_scale_counts,
        "stage_counts": stage_counts,
        "severity_counts": severity_counts,
        "unknown_counts": {
            "failure_type": unknown_failure_type_count,
            "model_scale": unknown_model_scale_count,
            "failure_stage": unknown_stage_count,
            "severity": unknown_severity_count,
        },
        "unique_failure_type_count": len([k for k, v in failure_counts.items() if v > 0]),
        "missing_failure_types": missing_failure_types,
        "missing_model_scales": missing_model_scales,
        "missing_stages": missing_stages,
        "blind_spots": blind_spots,
        "alerts": alerts,
    }


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Taxonomy Coverage",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_cases: `{payload.get('total_cases')}`",
        f"- catalog_count: `{payload.get('catalog_count')}`",
        f"- unique_failure_type_count: `{payload.get('unique_failure_type_count')}`",
        f"- missing_failure_types_count: `{len(payload.get('missing_failure_types') or [])}`",
        f"- missing_model_scales_count: `{len(payload.get('missing_model_scales') or [])}`",
        f"- missing_stages_count: `{len(payload.get('missing_stages') or [])}`",
        "",
        "## Blind Spots",
        "",
    ]
    blind_spots = payload.get("blind_spots") or []
    if isinstance(blind_spots, list) and blind_spots:
        for x in blind_spots:
            lines.append(f"- `{x}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Alerts", ""])
    alerts = payload.get("alerts") or []
    if isinstance(alerts, list) and alerts:
        for x in alerts:
            lines.append(f"- `{x}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute failure taxonomy coverage ledger")
    parser.add_argument(
        "--catalog",
        action="append",
        default=[],
        help="Failure catalog JSON path (supports repeated --catalog)",
    )
    parser.add_argument("--out", default="artifacts/dataset_failure_taxonomy_coverage/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    summary = _compute_summary(args.catalog)
    summary["generated_at_utc"] = now
    summary["sources"] = {"catalog_paths": args.catalog}
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "total_cases": summary.get("total_cases")}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
