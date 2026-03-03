from __future__ import annotations

import argparse
import json
import math
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
    return "".join(ch if ch.isalnum() else "_" for ch in t).strip("_") or default


def _extract_mutations(payload: dict) -> list[dict]:
    rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _ratio(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 2)


def _entropy(counts: dict[str, int]) -> float:
    total = float(sum(max(0, int(v)) for v in counts.values()))
    if total <= 0:
        return 0.0
    acc = 0.0
    for v in counts.values():
        c = max(0, int(v))
        if c <= 0:
            continue
        p = c / total
        acc -= p * math.log(p, 2)
    return round(acc, 6)


def _tvd(curr: dict[str, int], prev: dict[str, int]) -> float:
    keys = sorted(set(curr.keys()) | set(prev.keys()))
    curr_total = float(sum(max(0, int(curr.get(k, 0))) for k in keys))
    prev_total = float(sum(max(0, int(prev.get(k, 0))) for k in keys))
    if curr_total <= 0 or prev_total <= 0:
        return 0.0
    delta = 0.0
    for k in keys:
        p = max(0, int(curr.get(k, 0))) / curr_total
        q = max(0, int(prev.get(k, 0))) / prev_total
        delta += abs(p - q)
    return round(delta * 0.5, 6)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Distribution Stability Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- unique_failure_types: `{payload.get('unique_failure_types')}`",
        f"- failure_type_entropy: `{payload.get('failure_type_entropy')}`",
        f"- top1_share_pct: `{payload.get('top1_share_pct')}`",
        f"- distribution_drift_tvd: `{payload.get('distribution_drift_tvd')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guard failure distribution stability for mutation manifests")
    parser.add_argument("--current-mutation-manifest", required=True)
    parser.add_argument("--previous-mutation-manifest", default=None)
    parser.add_argument("--min-unique-failure-types", type=int, default=5)
    parser.add_argument("--min-failure-type-entropy", type=float, default=1.4)
    parser.add_argument("--max-top1-share-pct", type=float, default=60.0)
    parser.add_argument("--max-distribution-drift-tvd", type=float, default=0.25)
    parser.add_argument("--min-large-failure-type-coverage", type=int, default=4)
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_stability_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    current_payload = _load_json(args.current_mutation_manifest)
    previous_payload = _load_json(args.previous_mutation_manifest)
    current_rows = _extract_mutations(current_payload)
    previous_rows = _extract_mutations(previous_payload)

    reasons: list[str] = []
    if not current_payload:
        reasons.append("current_mutation_manifest_missing")
    if not current_rows:
        reasons.append("current_mutation_manifest_empty")

    curr_type_counts: dict[str, int] = {}
    curr_scale_counts: dict[str, int] = {"small": 0, "medium": 0, "large": 0, "other": 0}
    curr_large_types: set[str] = set()
    for row in current_rows:
        ftype = _slug(row.get("expected_failure_type"), default="unknown")
        scale = _slug(row.get("target_scale"), default="other")
        if scale not in {"small", "medium", "large"}:
            scale = "other"
        curr_type_counts[ftype] = curr_type_counts.get(ftype, 0) + 1
        curr_scale_counts[scale] = curr_scale_counts.get(scale, 0) + 1
        if scale == "large":
            curr_large_types.add(ftype)

    prev_type_counts: dict[str, int] = {}
    for row in previous_rows:
        ftype = _slug(row.get("expected_failure_type"), default="unknown")
        prev_type_counts[ftype] = prev_type_counts.get(ftype, 0) + 1

    total = float(sum(curr_type_counts.values()))
    top1 = max(curr_type_counts.values()) if curr_type_counts else 0
    unique_types = len(curr_type_counts)
    entropy = _entropy(curr_type_counts)
    top1_share_pct = _ratio(float(top1), total)
    distribution_drift_tvd = _tvd(curr_type_counts, prev_type_counts) if prev_type_counts else 0.0

    alerts: list[str] = []
    if unique_types < int(args.min_unique_failure_types):
        alerts.append("unique_failure_types_below_target")
    if entropy < float(args.min_failure_type_entropy):
        alerts.append("failure_type_entropy_below_target")
    if top1_share_pct > float(args.max_top1_share_pct):
        alerts.append("top1_failure_type_share_high")
    if prev_type_counts and distribution_drift_tvd > float(args.max_distribution_drift_tvd):
        alerts.append("distribution_drift_tvd_high")
    if len(curr_large_types) < int(args.min_large_failure_type_coverage):
        alerts.append("large_failure_type_coverage_low")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": int(total),
        "unique_failure_types": unique_types,
        "failure_type_entropy": round(entropy, 6),
        "top1_share_pct": top1_share_pct,
        "distribution_drift_tvd": distribution_drift_tvd,
        "large_failure_type_coverage": len(curr_large_types),
        "current_failure_type_counts": curr_type_counts,
        "previous_failure_type_counts": prev_type_counts,
        "current_scale_counts": curr_scale_counts,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "current_mutation_manifest": args.current_mutation_manifest,
            "previous_mutation_manifest": args.previous_mutation_manifest,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "unique_failure_types": unique_types,
                "distribution_drift_tvd": distribution_drift_tvd,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
