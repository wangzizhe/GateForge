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


def _ratio_pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 4)


def _stderr_has_signal(stderr: str) -> bool:
    return bool(re.search(r"(error|failed|assert|exception|undefined|division)", stderr.lower()))


def _extract_signal(obs: dict) -> tuple[bool, str]:
    rc = obs.get("final_return_code")
    if isinstance(rc, int) and rc != 0:
        return True, "nonzero_exit"
    attempts = obs.get("attempts") if isinstance(obs.get("attempts"), list) else []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        if bool(attempt.get("timed_out")):
            return True, "timeout"
        if _stderr_has_signal(str(attempt.get("stderr") or "")):
            return True, "stderr_signal"
    if _stderr_has_signal(str(obs.get("stderr") or "")):
        return True, "stderr_signal"
    return False, ""


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Failure Signal Authenticity Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- observed_mutations: `{payload.get('observed_mutations')}`",
        f"- failure_signal_count: `{payload.get('failure_signal_count')}`",
        f"- failure_signal_ratio_pct: `{payload.get('failure_signal_ratio_pct')}`",
        f"- expected_failure_type_signal_coverage_pct: `{payload.get('expected_failure_type_signal_coverage_pct')}`",
        f"- observed_coverage_ratio_pct: `{payload.get('observed_coverage_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit whether mutation runs produce real, observable failure signals")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--min-failure-signal-ratio-pct", type=float, default=1.0)
    parser.add_argument("--min-expected-failure-type-signal-coverage-pct", type=float, default=20.0)
    parser.add_argument("--min-observed-coverage-ratio-pct", type=float, default=95.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_failure_signal_authenticity_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not raw:
        reasons.append("mutation_raw_observations_missing")

    mutation_rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    observation_rows = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    mutations = [row for row in mutation_rows if isinstance(row, dict)]
    observations = [row for row in observation_rows if isinstance(row, dict)]

    if manifest and not mutations:
        reasons.append("mutation_manifest_empty")
    if raw and not observations:
        reasons.append("mutation_raw_observations_empty")

    obs_by_mutation_id = {str(row.get("mutation_id") or ""): row for row in observations if str(row.get("mutation_id") or "")}
    expected_types: set[str] = set()
    expected_types_with_signal: set[str] = set()
    signal_reason_counter: Counter[str] = Counter()
    signal_by_expected_type: Counter[str] = Counter()

    observed_mutations = 0
    failure_signal_count = 0
    for mutation in mutations:
        mutation_id = str(mutation.get("mutation_id") or "")
        expected_type = str(mutation.get("expected_failure_type") or mutation.get("failure_type") or "").strip()
        if expected_type:
            expected_types.add(expected_type)
        if not mutation_id:
            continue
        obs = obs_by_mutation_id.get(mutation_id)
        if not obs:
            continue
        observed_mutations += 1
        has_signal, signal_reason = _extract_signal(obs)
        if has_signal:
            failure_signal_count += 1
            if signal_reason:
                signal_reason_counter[signal_reason] += 1
            if expected_type:
                expected_types_with_signal.add(expected_type)
                signal_by_expected_type[expected_type] += 1

    total_mutations = len(mutations)
    observed_coverage_ratio_pct = _ratio_pct(observed_mutations, total_mutations)
    failure_signal_ratio_pct = _ratio_pct(failure_signal_count, observed_mutations)
    expected_failure_type_signal_coverage_pct = _ratio_pct(len(expected_types_with_signal), len(expected_types))

    alerts: list[str] = []
    if observed_coverage_ratio_pct < float(args.min_observed_coverage_ratio_pct):
        alerts.append("observed_coverage_ratio_below_threshold")
    if failure_signal_ratio_pct < float(args.min_failure_signal_ratio_pct):
        alerts.append("failure_signal_ratio_below_threshold")
    if expected_types and expected_failure_type_signal_coverage_pct < float(args.min_expected_failure_type_signal_coverage_pct):
        alerts.append("expected_failure_type_signal_coverage_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": total_mutations,
        "observed_mutations": observed_mutations,
        "failure_signal_count": failure_signal_count,
        "failure_signal_ratio_pct": failure_signal_ratio_pct,
        "expected_failure_type_count": len(expected_types),
        "expected_failure_type_with_signal_count": len(expected_types_with_signal),
        "expected_failure_type_signal_coverage_pct": expected_failure_type_signal_coverage_pct,
        "observed_coverage_ratio_pct": observed_coverage_ratio_pct,
        "signal_reason_counts": dict(signal_reason_counter),
        "signal_by_expected_failure_type": dict(signal_by_expected_type),
        "thresholds": {
            "min_failure_signal_ratio_pct": float(args.min_failure_signal_ratio_pct),
            "min_expected_failure_type_signal_coverage_pct": float(args.min_expected_failure_type_signal_coverage_pct),
            "min_observed_coverage_ratio_pct": float(args.min_observed_coverage_ratio_pct),
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
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
                "failure_signal_ratio_pct": failure_signal_ratio_pct,
                "expected_failure_type_signal_coverage_pct": expected_failure_type_signal_coverage_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
