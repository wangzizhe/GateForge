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


def _slug(v: object, *, default: str = "unknown") -> str:
    t = str(v or "").strip().lower()
    if not t:
        return default
    return t.replace("-", "_").replace(" ", "_")


def _extract_baseline_cases(pack: dict) -> list[dict]:
    rows = pack.get("selected_cases") if isinstance(pack.get("selected_cases"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _extract_validated_mutations(manifest: dict) -> list[dict]:
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _count_by(rows: list[dict], key: str, *, default: str = "unknown") -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        v = _slug(row.get(key), default=default)
        out[v] = out.get(v, 0) + 1
    return out


def _count_validated_failure_types(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        observed = str(row.get("observed_majority_failure_type") or "")
        expected = str(row.get("expected_failure_type") or "")
        v = _slug(observed or expected)
        out[v] = out.get(v, 0) + 1
    return out


def _normalize(counts: dict[str, int]) -> dict[str, float]:
    total = sum(max(0, int(v)) for v in counts.values())
    if total <= 0:
        return {}
    return {k: round(max(0, int(v)) / total, 6) for k, v in counts.items()}


def _l1_drift(before: dict[str, int], after: dict[str, int]) -> float:
    b = _normalize(before)
    a = _normalize(after)
    keys = set(b.keys()) | set(a.keys())
    return round(sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys) / 2.0, 6)


def _merge_counts(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + int(v)
    return out


def _share(counts: dict[str, int], key: str) -> float:
    total = sum(max(0, int(v)) for v in counts.values())
    if total <= 0:
        return 0.0
    return round(max(0, int(counts.get(key, 0))) / total * 100.0, 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Failure Distribution Benchmark v2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_cases_before: `{payload.get('total_cases_before')}`",
        f"- total_cases_after: `{payload.get('total_cases_after')}`",
        f"- failure_type_drift: `{payload.get('failure_type_drift')}`",
        f"- model_scale_drift: `{payload.get('model_scale_drift')}`",
        f"- validated_match_ratio_pct: `{payload.get('validated_match_ratio_pct')}`",
        f"- large_share_after_pct: `{payload.get('large_share_after_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark failure distribution using baseline pack plus validated mutation execution outcomes")
    parser.add_argument("--failure-baseline-pack", required=True)
    parser.add_argument("--mutation-validator-summary", required=True)
    parser.add_argument("--validated-mutation-manifest", required=True)
    parser.add_argument("--max-failure-type-drift", type=float, default=0.45)
    parser.add_argument("--max-model-scale-drift", type=float, default=0.4)
    parser.add_argument("--min-large-share-after-pct", type=float, default=18.0)
    parser.add_argument("--min-validated-match-ratio-pct", type=float, default=70.0)
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_benchmark_v2/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    baseline_pack = _load_json(args.failure_baseline_pack)
    validator_summary = _load_json(args.mutation_validator_summary)
    validated_manifest = _load_json(args.validated_mutation_manifest)

    reasons: list[str] = []
    if not baseline_pack:
        reasons.append("failure_baseline_pack_missing")
    if not validator_summary:
        reasons.append("mutation_validator_summary_missing")
    if not validated_manifest:
        reasons.append("validated_mutation_manifest_missing")

    baseline_cases = _extract_baseline_cases(baseline_pack)
    validated_rows = _extract_validated_mutations(validated_manifest)

    before_failure_types = _count_by(baseline_cases, "failure_type")
    before_scales = _count_by(baseline_cases, "model_scale")

    validated_failure_types = _count_validated_failure_types(validated_rows)
    validated_scales = _count_by(validated_rows, "target_scale", default="unknown")

    after_failure_types = _merge_counts(before_failure_types, validated_failure_types)
    after_scales = _merge_counts(before_scales, validated_scales)

    failure_type_drift = _l1_drift(before_failure_types, after_failure_types)
    model_scale_drift = _l1_drift(before_scales, after_scales)

    total_before = len(baseline_cases)
    total_after = sum(after_failure_types.values())

    validated_match_ratio = _to_float(validator_summary.get("expected_match_ratio_pct", 0.0))
    uncertain_count = _to_int(validator_summary.get("uncertain_count", 0))
    total_mutations = _to_int(validator_summary.get("total_mutations", 0))
    uncertain_ratio = round((uncertain_count / total_mutations) * 100.0, 2) if total_mutations > 0 else 0.0

    large_share_after = _share(after_scales, "large")

    alerts: list[str] = []
    if total_before == 0:
        alerts.append("baseline_pack_empty")
    if total_after == 0:
        alerts.append("combined_distribution_empty")
    if failure_type_drift > float(args.max_failure_type_drift):
        alerts.append("failure_type_drift_exceeds_threshold")
    if model_scale_drift > float(args.max_model_scale_drift):
        alerts.append("model_scale_drift_exceeds_threshold")
    if large_share_after < float(args.min_large_share_after_pct):
        alerts.append("large_share_after_below_threshold")
    if validated_match_ratio < float(args.min_validated_match_ratio_pct):
        alerts.append("validated_match_ratio_below_threshold")

    status = "PASS"
    if "failure_baseline_pack_missing" in reasons or "mutation_validator_summary_missing" in reasons or "validated_mutation_manifest_missing" in reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_cases_before": total_before,
        "total_cases_after": total_after,
        "failure_type_drift": failure_type_drift,
        "model_scale_drift": model_scale_drift,
        "validated_match_ratio_pct": validated_match_ratio,
        "uncertain_ratio_pct": uncertain_ratio,
        "large_share_after_pct": large_share_after,
        "distribution": {
            "failure_type_before": before_failure_types,
            "failure_type_after": after_failure_types,
            "model_scale_before": before_scales,
            "model_scale_after": after_scales,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_baseline_pack": args.failure_baseline_pack,
            "mutation_validator_summary": args.mutation_validator_summary,
            "validated_mutation_manifest": args.validated_mutation_manifest,
        },
    }

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "failure_type_drift": failure_type_drift, "model_scale_drift": model_scale_drift}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
