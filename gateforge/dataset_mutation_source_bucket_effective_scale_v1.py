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


def _norm_text(v: object) -> str:
    return str(v or "").strip()


def _ratio_pct(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 4)


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


def _infer_source_bucket(row: dict) -> str:
    src = Path(_norm_text(row.get("source_model_path") or row.get("model_path")))
    source_repo = _norm_text(row.get("source_repo")) or "repo_unknown"
    parent = src.parent.name.strip().lower() if src.parent.name else "root"
    grand = src.parent.parent.name.strip().lower() if src.parent.parent.name else "root"
    return f"{source_repo.lower()}:{grand}/{parent}"


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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Source-Bucket Effective Scale v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- source_bucket_count: `{payload.get('source_bucket_count')}`",
        f"- effective_mutations: `{payload.get('effective_mutations')}`",
        f"- weighted_effective_mutations: `{payload.get('weighted_effective_mutations')}`",
        f"- max_bucket_share_pct: `{payload.get('max_bucket_share_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute source-bucket effective mutation scale and concentration")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--mutation-effective-scale-summary", default=None)
    parser.add_argument("--min-source-buckets", type=int, default=2)
    parser.add_argument("--max-source-bucket-share-pct", type=float, default=70.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_source_bucket_effective_scale_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)
    effective_scale = _load_json(args.mutation_effective_scale_summary)

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

    obs_by_mutation = {str(row.get("mutation_id") or ""): row for row in observations if str(row.get("mutation_id") or "")}
    signature_counts: Counter[str] = Counter(_signature(row) for row in mutations)
    seen_signatures: set[str] = set()

    buckets: dict[str, dict] = {}
    for row in mutations:
        mutation_id = str(row.get("mutation_id") or "").strip()
        bucket_name = _infer_source_bucket(row)
        bucket = buckets.setdefault(
            bucket_name,
            {
                "source_bucket": bucket_name,
                "planned_mutations": 0,
                "executed_mutations": 0,
                "effective_mutations": 0,
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
        sig = _signature(row)
        if sig and signature_counts.get(sig, 0) > 1 and sig in seen_signatures:
            continue
        if sig:
            seen_signatures.add(sig)
        bucket["effective_mutations"] = _to_int(bucket.get("effective_mutations", 0)) + 1

    bucket_rows = sorted(buckets.values(), key=lambda x: (-_to_int(x.get("effective_mutations", 0)), str(x.get("source_bucket") or "")))
    total_planned = sum(_to_int(x.get("planned_mutations", 0)) for x in bucket_rows)
    total_executed = sum(_to_int(x.get("executed_mutations", 0)) for x in bucket_rows)
    total_effective = sum(_to_int(x.get("effective_mutations", 0)) for x in bucket_rows)
    source_bucket_count = len(bucket_rows)

    multiplier = _to_float(effective_scale.get("authenticity_multiplier", 1.0)) if effective_scale else 1.0
    if multiplier <= 0:
        multiplier = 0.0
    weighted_effective_mutations = round(total_effective * multiplier, 4)
    max_bucket_effective = max((_to_int(x.get("effective_mutations", 0)) for x in bucket_rows), default=0)
    max_bucket_share_pct = _ratio_pct(float(max_bucket_effective), float(max(1, total_effective)))

    top_source_buckets = []
    for row in bucket_rows[:12]:
        eff = _to_int(row.get("effective_mutations", 0))
        top_source_buckets.append(
            {
                "source_bucket": row.get("source_bucket"),
                "planned_mutations": _to_int(row.get("planned_mutations", 0)),
                "executed_mutations": _to_int(row.get("executed_mutations", 0)),
                "effective_mutations": eff,
                "effective_share_pct": _ratio_pct(float(eff), float(max(1, total_effective))),
            }
        )

    alerts: list[str] = []
    if source_bucket_count < int(args.min_source_buckets):
        alerts.append("source_bucket_coverage_below_threshold")
    if max_bucket_share_pct > float(args.max_source_bucket_share_pct):
        alerts.append("source_bucket_concentration_above_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_bucket_count": source_bucket_count,
        "planned_mutations": total_planned,
        "executed_mutations": total_executed,
        "effective_mutations": total_effective,
        "weighted_effective_mutations": weighted_effective_mutations,
        "authenticity_multiplier_used": round(multiplier, 8),
        "max_bucket_share_pct": round(max_bucket_share_pct, 4),
        "top_source_buckets": top_source_buckets,
        "thresholds": {
            "min_source_buckets": int(args.min_source_buckets),
            "max_source_bucket_share_pct": float(args.max_source_bucket_share_pct),
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
            "mutation_effective_scale_summary": args.mutation_effective_scale_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "source_bucket_count": source_bucket_count,
                "effective_mutations": total_effective,
                "max_bucket_share_pct": round(max_bucket_share_pct, 4),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
