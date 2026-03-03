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


def _entropy(counter: dict[str, int]) -> float:
    total = sum(max(0, v) for v in counter.values())
    if total <= 0:
        return 0.0
    value = 0.0
    for v in counter.values():
        if v <= 0:
            continue
        p = v / total
        value -= p * math.log(p, 2)
    return round(value, 4)


def _max_share(counter: dict[str, int]) -> float:
    total = sum(max(0, v) for v in counter.values())
    if total <= 0:
        return 0.0
    return round(max(counter.values()) / total, 4) if counter else 0.0


def _tvd(a: dict[str, int], b: dict[str, int]) -> float:
    keys = set(a.keys()) | set(b.keys())
    at = sum(max(0, v) for v in a.values())
    bt = sum(max(0, v) for v in b.values())
    if at <= 0 or bt <= 0:
        return 0.0
    diff = 0.0
    for k in keys:
        pa = max(0, a.get(k, 0)) / at
        pb = max(0, b.get(k, 0)) / bt
        diff += abs(pa - pb)
    return round(diff * 0.5, 6)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Failure Type Balance Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- expected_failure_type_count: `{payload.get('expected_failure_type_count')}`",
        f"- expected_entropy: `{payload.get('expected_entropy')}`",
        f"- expected_max_share: `{payload.get('expected_max_share')}`",
        f"- expected_vs_observed_tvd: `{payload.get('expected_vs_observed_tvd')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check mutation failure type distribution balance and drift")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-validation-records", default=None)
    parser.add_argument("--min-failure-types", type=int, default=4)
    parser.add_argument("--min-entropy", type=float, default=1.8)
    parser.add_argument("--max-dominant-share", type=float, default=0.45)
    parser.add_argument("--max-expected-vs-observed-tvd", type=float, default=0.35)
    parser.add_argument("--out", default="artifacts/dataset_mutation_failure_type_balance_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    records = _load_json(args.mutation_validation_records)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")

    expected_counter: dict[str, int] = {}
    for row in manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []:
        if not isinstance(row, dict):
            continue
        expected = str(row.get("expected_failure_type") or "unknown")
        expected_counter[expected] = expected_counter.get(expected, 0) + 1

    observed_counter: dict[str, int] = {}
    for row in records.get("records") if isinstance(records.get("records"), list) else []:
        if not isinstance(row, dict):
            continue
        observed = str(row.get("observed_failure_type") or "")
        if not observed:
            continue
        observed_counter[observed] = observed_counter.get(observed, 0) + 1

    expected_type_count = len([k for k, v in expected_counter.items() if v > 0 and k != "unknown"])
    expected_entropy = _entropy(expected_counter)
    expected_max_share = _max_share(expected_counter)
    expected_vs_observed_tvd = _tvd(expected_counter, observed_counter) if observed_counter else 0.0

    alerts: list[str] = []
    if not expected_counter:
        alerts.append("expected_failure_types_missing")
    if expected_type_count < int(args.min_failure_types):
        alerts.append("failure_type_count_below_threshold")
    if expected_entropy < float(args.min_entropy):
        alerts.append("expected_entropy_low")
    if expected_max_share > float(args.max_dominant_share):
        alerts.append("dominant_failure_type_share_high")
    if observed_counter and expected_vs_observed_tvd > float(args.max_expected_vs_observed_tvd):
        alerts.append("expected_vs_observed_distribution_drift_high")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "expected_failure_type_count": expected_type_count,
        "expected_entropy": expected_entropy,
        "expected_max_share": expected_max_share,
        "expected_vs_observed_tvd": expected_vs_observed_tvd,
        "expected_distribution": expected_counter,
        "observed_distribution": observed_counter,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_validation_records": args.mutation_validation_records,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "expected_failure_type_count": expected_type_count, "expected_entropy": expected_entropy}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
