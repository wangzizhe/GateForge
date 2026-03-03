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


def _ratio(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    pos = max(0.0, min(1.0, q)) * float(len(arr) - 1)
    lo = int(pos)
    hi = min(len(arr) - 1, lo + 1)
    if lo == hi:
        return float(arr[lo])
    frac = pos - float(lo)
    return float(arr[lo] * (1.0 - frac) + arr[hi] * frac)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Repro Depth Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- tracked_models: `{payload.get('tracked_models')}`",
        f"- large_models: `{payload.get('large_models')}`",
        f"- models_meeting_depth_threshold: `{payload.get('models_meeting_depth_threshold')}`",
        f"- large_models_meeting_depth_threshold: `{payload.get('large_models_meeting_depth_threshold')}`",
        f"- p10_reproducible_mutations_per_model: `{payload.get('p10_reproducible_mutations_per_model')}`",
        f"- max_model_share_pct: `{payload.get('max_model_share_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard mutation reproducibility depth distribution across selected real models")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--selection-plan", default=None)
    parser.add_argument("--min-reproducible-mutations-per-model", type=int, default=6)
    parser.add_argument("--min-large-model-reproducible-mutations-per-model", type=int, default=8)
    parser.add_argument("--min-models-meeting-threshold-ratio-pct", type=float, default=80.0)
    parser.add_argument("--max-top-model-share-pct", type=float, default=35.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_repro_depth_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    observations = _load_json(args.mutation_raw_observations)
    selection_plan = _load_json(args.selection_plan)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not observations:
        reasons.append("mutation_raw_observations_missing")

    mutation_rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    obs_rows = observations.get("observations") if isinstance(observations.get("observations"), list) else []
    selected_model_ids = selection_plan.get("selected_model_ids") if isinstance(selection_plan.get("selected_model_ids"), list) else []
    selected_model_ids = {str(x).strip() for x in selected_model_ids if str(x).strip()}

    obs_by_mutation: dict[str, dict] = {}
    for row in obs_rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if mutation_id:
            obs_by_mutation[mutation_id] = row

    per_model: dict[str, dict] = {}
    for row in mutation_rows:
        if not isinstance(row, dict):
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        model_id = str(row.get("target_model_id") or row.get("model_id") or "").strip()
        if not model_id:
            continue
        if selected_model_ids and model_id not in selected_model_ids:
            continue
        scale = str(row.get("target_scale") or "small").strip().lower()
        bucket = per_model.setdefault(
            model_id,
            {"model_id": model_id, "target_scale": scale, "planned_mutations": 0, "reproducible_mutations": 0, "infra_error_mutations": 0},
        )
        bucket["planned_mutations"] = _to_int(bucket.get("planned_mutations", 0)) + 1
        obs = obs_by_mutation.get(mutation_id, {})
        execution_status = str(obs.get("execution_status") or "")
        final_rc = obs.get("final_return_code")
        if execution_status == "EXECUTED" and isinstance(final_rc, int):
            bucket["reproducible_mutations"] = _to_int(bucket.get("reproducible_mutations", 0)) + 1
        else:
            bucket["infra_error_mutations"] = _to_int(bucket.get("infra_error_mutations", 0)) + 1

    model_rows = sorted(per_model.values(), key=lambda x: str(x.get("model_id") or ""))
    tracked_models = len(model_rows)
    large_rows = [x for x in model_rows if str(x.get("target_scale") or "") == "large"]
    large_models = len(large_rows)
    min_depth = max(1, int(args.min_reproducible_mutations_per_model))
    min_large_depth = max(1, int(args.min_large_model_reproducible_mutations_per_model))

    models_meeting_depth = len([x for x in model_rows if _to_int(x.get("reproducible_mutations", 0)) >= min_depth])
    large_models_meeting_depth = len([x for x in large_rows if _to_int(x.get("reproducible_mutations", 0)) >= min_large_depth])
    models_meeting_depth_ratio_pct = _ratio(float(models_meeting_depth), float(max(1, tracked_models)))
    large_models_meeting_depth_ratio_pct = _ratio(float(large_models_meeting_depth), float(max(1, large_models)))
    total_reproducible = sum(_to_int(x.get("reproducible_mutations", 0)) for x in model_rows)
    top_model_reproducible = max([_to_int(x.get("reproducible_mutations", 0)) for x in model_rows], default=0)
    max_model_share_pct = _ratio(float(top_model_reproducible), float(max(1, total_reproducible)))
    depth_values = [_to_int(x.get("reproducible_mutations", 0)) for x in model_rows]
    p10_depth = round(_percentile(depth_values, 0.10), 4)
    p50_depth = round(_percentile(depth_values, 0.50), 4)

    alerts: list[str] = []
    if tracked_models == 0:
        alerts.append("tracked_models_empty")
    if models_meeting_depth_ratio_pct < float(args.min_models_meeting_threshold_ratio_pct):
        alerts.append("models_meeting_depth_ratio_below_threshold")
    if large_models > 0 and large_models_meeting_depth_ratio_pct < float(args.min_models_meeting_threshold_ratio_pct):
        alerts.append("large_models_meeting_depth_ratio_below_threshold")
    if max_model_share_pct > float(args.max_top_model_share_pct):
        alerts.append("reproducibility_concentration_too_high")
    if p10_depth < float(min_depth):
        alerts.append("tail_model_repro_depth_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "tracked_models": tracked_models,
        "large_models": large_models,
        "models_meeting_depth_threshold": models_meeting_depth,
        "large_models_meeting_depth_threshold": large_models_meeting_depth,
        "models_meeting_depth_ratio_pct": models_meeting_depth_ratio_pct,
        "large_models_meeting_depth_ratio_pct": large_models_meeting_depth_ratio_pct,
        "total_reproducible_mutations": total_reproducible,
        "max_model_share_pct": max_model_share_pct,
        "p10_reproducible_mutations_per_model": p10_depth,
        "p50_reproducible_mutations_per_model": p50_depth,
        "per_model_depth": model_rows,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
            "selection_plan": args.selection_plan,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "tracked_models": tracked_models,
                "models_meeting_depth_threshold": models_meeting_depth,
                "p10_reproducible_mutations_per_model": p10_depth,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
