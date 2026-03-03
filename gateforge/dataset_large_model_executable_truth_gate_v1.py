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


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Large Model Executable Truth Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- large_model_count: `{payload.get('large_model_count')}`",
        f"- large_model_check_pass_rate_pct: `{payload.get('large_model_check_pass_rate_pct')}`",
        f"- large_model_repro_execution_rate_pct: `{payload.get('large_model_repro_execution_rate_pct')}`",
        f"- large_executable_real_rate_pct: `{payload.get('large_executable_real_rate_pct')}`",
        f"- large_executable_real_count: `{payload.get('large_executable_real_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-check large model baseline checks and reproducible mutation execution")
    parser.add_argument("--executable-registry", required=True)
    parser.add_argument("--mutation-validation-records", required=True)
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--min-large-check-pass-rate-pct", type=float, default=85.0)
    parser.add_argument("--min-large-executable-real-rate-pct", type=float, default=70.0)
    parser.add_argument("--out", default="artifacts/dataset_large_model_executable_truth_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.executable_registry)
    validation_records = _load_json(args.mutation_validation_records)
    manifest = _load_json(args.mutation_manifest)
    observations = _load_json(args.mutation_raw_observations)
    reasons: list[str] = []
    if not registry:
        reasons.append("executable_registry_missing")
    if not validation_records:
        reasons.append("mutation_validation_records_missing")
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not observations:
        reasons.append("mutation_raw_observations_missing")

    model_rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    large_rows = [
        r
        for r in model_rows
        if isinstance(r, dict)
        and str(r.get("asset_type") or "") == "model_source"
        and str(r.get("suggested_scale") or "").strip().lower() == "large"
    ]
    large_model_ids = {str(r.get("model_id") or "").strip() for r in large_rows if str(r.get("model_id") or "").strip()}
    large_source_to_model = {
        str(r.get("source_path") or "").strip(): str(r.get("model_id") or "").strip()
        for r in large_rows
        if str(r.get("source_path") or "").strip() and str(r.get("model_id") or "").strip()
    }
    large_model_count = len(large_model_ids)

    baseline_records = (
        validation_records.get("baseline_records") if isinstance(validation_records.get("baseline_records"), list) else []
    )
    check_pass_models: set[str] = set()
    for row in baseline_records:
        if not isinstance(row, dict):
            continue
        source_path = str(row.get("source_model_path") or "").strip()
        model_id = large_source_to_model.get(source_path, "")
        if not model_id:
            continue
        if bool(row.get("check_ok")):
            check_pass_models.add(model_id)

    mutation_rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    mutation_to_model: dict[str, str] = {}
    for row in mutation_rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        model_id = str(row.get("target_model_id") or "").strip()
        scale = str(row.get("target_scale") or "").strip().lower()
        if mutation_id and model_id and model_id in large_model_ids and scale == "large":
            mutation_to_model[mutation_id] = model_id

    obs_rows = observations.get("observations") if isinstance(observations.get("observations"), list) else []
    repro_execution_models: set[str] = set()
    for row in obs_rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        model_id = mutation_to_model.get(mutation_id, "")
        if not model_id:
            continue
        execution_status = str(row.get("execution_status") or "")
        final_rc = row.get("final_return_code")
        if execution_status == "EXECUTED" and isinstance(final_rc, int):
            repro_execution_models.add(model_id)

    large_executable_real_models = sorted(check_pass_models.intersection(repro_execution_models))
    large_executable_real_count = len(large_executable_real_models)
    check_pass_rate = _ratio(len(check_pass_models), large_model_count)
    repro_execution_rate = _ratio(len(repro_execution_models), large_model_count)
    large_executable_real_rate = _ratio(large_executable_real_count, large_model_count)

    alerts: list[str] = []
    if large_model_count == 0:
        alerts.append("large_model_count_zero")
    if check_pass_rate < float(args.min_large_check_pass_rate_pct):
        alerts.append("large_model_check_pass_rate_below_threshold")
    if large_executable_real_rate < float(args.min_large_executable_real_rate_pct):
        alerts.append("large_executable_real_rate_below_threshold")
    if len(check_pass_models) > 0 and len(repro_execution_models) == 0:
        alerts.append("large_models_without_repro_execution")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "large_model_count": large_model_count,
        "large_model_check_pass_count": len(check_pass_models),
        "large_model_check_pass_rate_pct": check_pass_rate,
        "large_model_repro_execution_count": len(repro_execution_models),
        "large_model_repro_execution_rate_pct": repro_execution_rate,
        "large_executable_real_count": large_executable_real_count,
        "large_executable_real_rate_pct": large_executable_real_rate,
        "large_executable_real_models": large_executable_real_models[:120],
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "executable_registry": args.executable_registry,
            "mutation_validation_records": args.mutation_validation_records,
            "mutation_manifest": args.mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "large_model_count": large_model_count,
                "large_executable_real_count": large_executable_real_count,
                "large_executable_real_rate_pct": large_executable_real_rate,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
