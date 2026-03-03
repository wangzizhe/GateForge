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


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Real Model Source Diversity Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_models: `{payload.get('total_models')}`",
        f"- unique_source_repos: `{payload.get('unique_source_repos')}`",
        f"- unique_source_buckets: `{payload.get('unique_source_buckets')}`",
        f"- max_source_bucket_share_pct: `{payload.get('max_source_bucket_share_pct')}`",
        f"- unique_source_buckets_for_large_models: `{payload.get('unique_source_buckets_for_large_models')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _source_bucket(row: dict) -> str:
    source_path = Path(str(row.get("source_path") or ""))
    source_repo = str(row.get("source_repo") or "").strip().lower() or "repo_unknown"
    parent = source_path.parent.name.strip().lower() or "root"
    grand = source_path.parent.parent.name.strip().lower() or "root"
    return f"{source_repo}:{grand}/{parent}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard real model pool source diversity")
    parser.add_argument("--executable-registry", required=True)
    parser.add_argument("--min-source-repos", type=int, default=2)
    parser.add_argument("--min-source-buckets", type=int, default=4)
    parser.add_argument("--min-source-buckets-for-large-models", type=int, default=2)
    parser.add_argument("--max-source-bucket-share-pct", type=float, default=65.0)
    parser.add_argument("--out", default="artifacts/dataset_real_model_source_diversity_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    registry = _load_json(args.executable_registry)
    reasons: list[str] = []
    if not registry:
        reasons.append("executable_registry_missing")

    rows = registry.get("models") if isinstance(registry.get("models"), list) else []
    models = [x for x in rows if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source"]
    total_models = len(models)

    repo_counts: dict[str, int] = {}
    bucket_counts: dict[str, int] = {}
    large_bucket_counts: dict[str, int] = {}
    for row in models:
        repo = str(row.get("source_repo") or "").strip().lower() or "repo_unknown"
        bucket = _source_bucket(row)
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        if str(row.get("suggested_scale") or "").strip().lower() == "large":
            large_bucket_counts[bucket] = large_bucket_counts.get(bucket, 0) + 1

    unique_source_repos = len(repo_counts)
    unique_source_buckets = len(bucket_counts)
    unique_source_buckets_for_large_models = len(large_bucket_counts)
    max_bucket_count = max(bucket_counts.values()) if bucket_counts else 0
    max_source_bucket_share_pct = _ratio(max_bucket_count, total_models)

    top_source_buckets = sorted(
        [{"source_bucket": k, "model_count": v, "share_pct": _ratio(v, total_models)} for k, v in bucket_counts.items()],
        key=lambda x: (-_to_int(x.get("model_count", 0)), str(x.get("source_bucket") or "")),
    )[:10]

    alerts: list[str] = []
    if total_models == 0:
        alerts.append("total_models_zero")
    if unique_source_repos < int(args.min_source_repos):
        alerts.append("source_repo_diversity_below_threshold")
    if unique_source_buckets < int(args.min_source_buckets):
        alerts.append("source_bucket_diversity_below_threshold")
    if unique_source_buckets_for_large_models < int(args.min_source_buckets_for_large_models):
        alerts.append("large_model_source_bucket_diversity_below_threshold")
    if max_source_bucket_share_pct > float(args.max_source_bucket_share_pct):
        alerts.append("source_bucket_concentration_above_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_models": total_models,
        "unique_source_repos": unique_source_repos,
        "unique_source_buckets": unique_source_buckets,
        "unique_source_buckets_for_large_models": unique_source_buckets_for_large_models,
        "max_source_bucket_share_pct": max_source_bucket_share_pct,
        "top_source_buckets": top_source_buckets,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {"executable_registry": args.executable_registry},
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_models": total_models,
                "unique_source_buckets": unique_source_buckets,
                "max_source_bucket_share_pct": max_source_bucket_share_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
