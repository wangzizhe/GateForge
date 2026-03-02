from __future__ import annotations

import argparse
import hashlib
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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    return 0


def _freeze_id(parts: list[str]) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"failure-freeze-{digest[:12]}"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    locked = payload.get("locked_metrics") if isinstance(payload.get("locked_metrics"), dict) else {}
    lines = [
        "# GateForge Failure Distribution Baseline Freeze v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- freeze_id: `{payload.get('freeze_id')}`",
        f"- baseline_id: `{payload.get('baseline_id')}`",
        "",
        "## Locked Metrics",
        "",
        f"- total_cases_after: `{locked.get('total_cases_after')}`",
        f"- failure_type_drift: `{locked.get('failure_type_drift')}`",
        f"- model_scale_drift: `{locked.get('model_scale_drift')}`",
        f"- failure_distribution_stability_score: `{locked.get('failure_distribution_stability_score')}`",
        f"- unique_failure_types: `{locked.get('unique_failure_types')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze failure distribution baseline metrics for stable delta comparisons")
    parser.add_argument("--moat-scorecard-baseline-summary", required=True)
    parser.add_argument("--failure-distribution-benchmark-summary", required=True)
    parser.add_argument("--failure-distribution-quality-gate-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_failure_distribution_baseline_freeze_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scorecard = _load_json(args.moat_scorecard_baseline_summary)
    benchmark = _load_json(args.failure_distribution_benchmark_summary)
    quality_gate = _load_json(args.failure_distribution_quality_gate_summary)

    reasons: list[str] = []
    if not scorecard:
        reasons.append("moat_scorecard_baseline_summary_missing")
    if not benchmark:
        reasons.append("failure_distribution_benchmark_summary_missing")
    if not quality_gate:
        reasons.append("failure_distribution_quality_gate_summary_missing")

    baseline_id = str(scorecard.get("baseline_id") or "")
    total_cases_after = _to_int(benchmark.get("total_cases_after", 0))
    failure_type_drift = _to_float(benchmark.get("failure_type_drift", 0.0))
    model_scale_drift = _to_float(benchmark.get("model_scale_drift", 0.0))
    stability_score = _to_float(scorecard.get("failure_distribution_stability_score", 0.0))
    unique_failure_types = _to_int(quality_gate.get("unique_failure_types", 0))
    gate_result = str(quality_gate.get("gate_result") or "UNKNOWN")

    locked_metrics = {
        "total_cases_after": total_cases_after,
        "failure_type_drift": round(failure_type_drift, 6),
        "model_scale_drift": round(model_scale_drift, 6),
        "failure_distribution_stability_score": round(stability_score, 2),
        "unique_failure_types": unique_failure_types,
    }

    comparator_policy = {
        "delta_mode": "same_metric_same_formula",
        "drift_tolerance": 0.05,
        "stability_score_floor": 75.0,
        "min_unique_failure_types": 4,
    }

    freeze_id = _freeze_id(
        [
            baseline_id,
            str(total_cases_after),
            str(locked_metrics["failure_type_drift"]),
            str(locked_metrics["model_scale_drift"]),
            str(locked_metrics["failure_distribution_stability_score"]),
            str(unique_failure_types),
        ]
    )

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif gate_result != "PASS":
        status = "NEEDS_REVIEW"
        reasons.append("quality_gate_not_pass")
    elif failure_type_drift > comparator_policy["drift_tolerance"] or model_scale_drift > comparator_policy["drift_tolerance"]:
        status = "NEEDS_REVIEW"
        reasons.append("drift_above_tolerance")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "freeze_id": freeze_id,
        "baseline_id": baseline_id,
        "version": "v1",
        "locked_metrics": locked_metrics,
        "comparator_policy": comparator_policy,
        "sources": {
            "moat_scorecard_baseline_summary": args.moat_scorecard_baseline_summary,
            "failure_distribution_benchmark_summary": args.failure_distribution_benchmark_summary,
            "failure_distribution_quality_gate_summary": args.failure_distribution_quality_gate_summary,
        },
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "freeze_id": freeze_id}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
