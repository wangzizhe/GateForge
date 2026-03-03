from __future__ import annotations

import argparse
import json
import re
from collections import Counter
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


def _norm_text(v: object) -> str:
    return str(v or "").strip()


def _signature(row: dict) -> str:
    model_id = _norm_text(row.get("target_model_id") or row.get("model_id"))
    if not model_id:
        model_id = Path(_norm_text(row.get("source_model_path") or row.get("model_path") or row.get("mutated_model_path"))).stem
    return "|".join(
        [
            model_id,
            _norm_text(row.get("target_scale")),
            _norm_text(row.get("failure_type") or row.get("expected_failure_type")),
            _norm_text(row.get("operator")),
            _norm_text(row.get("expected_stage")),
            _norm_text(row.get("seed")),
        ]
    )


def _is_solver_command(command: str) -> bool:
    c = command.lower()
    tokens = (" omc ", "openmodelica", ".mos", "checkmodel(", "simulate(", "buildmodel(")
    cpad = f" {c} "
    return any(t in cpad or t in c for t in tokens)


def _has_failure_signal(obs: dict) -> bool:
    rc = obs.get("final_return_code")
    if isinstance(rc, int) and rc != 0:
        return True
    attempts = obs.get("attempts") if isinstance(obs.get("attempts"), list) else []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        if bool(attempt.get("timed_out")):
            return True
        stderr = str(attempt.get("stderr") or "").lower()
        if re.search(r"(error|failed|assert|exception|undefined|division)", stderr):
            return True
    return False


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Effective Depth Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- tracked_models: `{payload.get('tracked_models')}`",
        f"- large_models: `{payload.get('large_models')}`",
        f"- total_effective_mutations: `{payload.get('total_effective_mutations')}`",
        f"- p10_effective_mutations_per_model: `{payload.get('p10_effective_mutations_per_model')}`",
        f"- models_meeting_effective_depth_ratio_pct: `{payload.get('models_meeting_effective_depth_ratio_pct')}`",
        f"- large_models_meeting_effective_depth_ratio_pct: `{payload.get('large_models_meeting_effective_depth_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard effective mutation depth distribution across real models")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--selection-plan", default=None)
    parser.add_argument("--min-effective-mutations-per-model", type=int, default=1)
    parser.add_argument("--min-large-effective-mutations-per-model", type=int, default=1)
    parser.add_argument("--min-models-meeting-threshold-ratio-pct", type=float, default=50.0)
    parser.add_argument("--max-top-model-share-pct", type=float, default=45.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_effective_depth_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)
    selection_plan = _load_json(args.selection_plan)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not raw:
        reasons.append("mutation_raw_observations_missing")

    mutation_rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    obs_rows = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    mutations = [x for x in mutation_rows if isinstance(x, dict)]
    observations = [x for x in obs_rows if isinstance(x, dict)]

    if manifest and not mutations:
        reasons.append("mutation_manifest_empty")
    if raw and not observations:
        reasons.append("mutation_raw_observations_empty")

    selected_model_ids = selection_plan.get("selected_model_ids") if isinstance(selection_plan.get("selected_model_ids"), list) else []
    selected_model_ids = {str(x or "").strip() for x in selected_model_ids if str(x or "").strip()}

    obs_by_mutation = {str(row.get("mutation_id") or ""): row for row in observations if str(row.get("mutation_id") or "")}
    signature_counter: Counter[str] = Counter(_signature(row) for row in mutations)

    per_model: dict[str, dict] = {}
    seen_unique_signatures: set[str] = set()
    for row in mutations:
        mutation_id = str(row.get("mutation_id") or "").strip()
        model_id = str(row.get("target_model_id") or row.get("model_id") or "").strip()
        if not model_id:
            continue
        if selected_model_ids and model_id not in selected_model_ids:
            continue
        scale = str(row.get("target_scale") or "small").strip().lower()
        bucket = per_model.setdefault(
            model_id,
            {
                "model_id": model_id,
                "target_scale": scale,
                "planned_mutations": 0,
                "effective_mutations": 0,
                "executed_mutations": 0,
            },
        )
        bucket["planned_mutations"] = _to_int(bucket.get("planned_mutations", 0)) + 1
        if not mutation_id:
            continue
        obs = obs_by_mutation.get(mutation_id, {})
        if str(obs.get("execution_status") or "") != "EXECUTED":
            continue
        bucket["executed_mutations"] = _to_int(bucket.get("executed_mutations", 0)) + 1
        if not _is_solver_command(str(row.get("repro_command") or "")):
            continue
        if not _has_failure_signal(obs):
            continue
        signature = _signature(row)
        if not signature:
            continue
        if signature_counter.get(signature, 0) > 1 and signature in seen_unique_signatures:
            continue
        seen_unique_signatures.add(signature)
        bucket["effective_mutations"] = _to_int(bucket.get("effective_mutations", 0)) + 1

    model_rows = sorted(per_model.values(), key=lambda x: str(x.get("model_id") or ""))
    tracked_models = len(model_rows)
    large_rows = [x for x in model_rows if str(x.get("target_scale") or "") == "large"]
    large_models = len(large_rows)
    min_depth = max(1, int(args.min_effective_mutations_per_model))
    min_large_depth = max(1, int(args.min_large_effective_mutations_per_model))

    models_meeting_depth = len([x for x in model_rows if _to_int(x.get("effective_mutations", 0)) >= min_depth])
    large_models_meeting_depth = len([x for x in large_rows if _to_int(x.get("effective_mutations", 0)) >= min_large_depth])
    models_meeting_ratio_pct = _ratio(float(models_meeting_depth), float(max(1, tracked_models)))
    large_models_meeting_ratio_pct = _ratio(float(large_models_meeting_depth), float(max(1, large_models)))

    total_effective = sum(_to_int(x.get("effective_mutations", 0)) for x in model_rows)
    top_model_effective = max([_to_int(x.get("effective_mutations", 0)) for x in model_rows], default=0)
    max_model_share_pct = _ratio(float(top_model_effective), float(max(1, total_effective)))
    depth_values = [_to_int(x.get("effective_mutations", 0)) for x in model_rows]
    p10_depth = round(_percentile(depth_values, 0.10), 4)
    p50_depth = round(_percentile(depth_values, 0.50), 4)

    alerts: list[str] = []
    if tracked_models == 0:
        alerts.append("tracked_models_empty")
    if models_meeting_ratio_pct < float(args.min_models_meeting_threshold_ratio_pct):
        alerts.append("models_meeting_effective_depth_ratio_below_threshold")
    if large_models > 0 and large_models_meeting_ratio_pct < float(args.min_models_meeting_threshold_ratio_pct):
        alerts.append("large_models_meeting_effective_depth_ratio_below_threshold")
    if max_model_share_pct > float(args.max_top_model_share_pct):
        alerts.append("effective_depth_concentration_too_high")
    if p10_depth < float(min_depth):
        alerts.append("tail_model_effective_depth_below_threshold")

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
        "models_meeting_effective_depth_threshold": models_meeting_depth,
        "large_models_meeting_effective_depth_threshold": large_models_meeting_depth,
        "models_meeting_effective_depth_ratio_pct": models_meeting_ratio_pct,
        "large_models_meeting_effective_depth_ratio_pct": large_models_meeting_ratio_pct,
        "total_effective_mutations": total_effective,
        "max_model_share_pct": max_model_share_pct,
        "p10_effective_mutations_per_model": p10_depth,
        "p50_effective_mutations_per_model": p50_depth,
        "per_model_effective_depth": model_rows,
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
                "total_effective_mutations": total_effective,
                "p10_effective_mutations_per_model": p10_depth,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
