from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_STEPS = [
    "replay_observation_store",
    "failure_label_calibrator",
    "mutation_execution_validator",
    "failure_distribution_benchmark_v2",
]


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


def _status(payload: dict) -> str:
    return str(payload.get("status") or "UNKNOWN")


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _step_row(step_id: str, payload: dict, source: str | None) -> dict:
    st = _status(payload)
    state = "OK" if st == "PASS" else ("ATTN" if st == "NEEDS_REVIEW" else "BLOCKED")
    return {
        "step_id": step_id,
        "status": st,
        "state": state,
        "source": source,
    }


def _build_score(
    store: dict,
    calibrator: dict,
    validator: dict,
    benchmark: dict,
    release: dict,
    large_push: dict,
) -> tuple[float, dict[str, float]]:
    ingested = _to_int(store.get("ingested_records", 0))
    calibrator_match = _to_float(calibrator.get("expected_match_ratio_pct", 0.0))
    validator_match = _to_float(validator.get("expected_match_ratio_pct", 0.0))
    drift = _to_float(benchmark.get("failure_type_drift", 1.0))
    release_score = _to_float(release.get("public_release_score", 50.0))
    push_target = _to_int(large_push.get("push_target_large_cases", 0))

    components = {
        "store_signal": _clamp(25.0 if ingested > 0 else 12.0),
        "calibrator_signal": _clamp(calibrator_match * 0.22),
        "validator_signal": _clamp(validator_match * 0.26),
        "distribution_signal": _clamp(28.0 - (drift * 40.0)),
        "public_signal": _clamp(release_score * 0.18),
        "coverage_debt_penalty": _clamp(push_target * 1.2, 0.0, 12.0),
    }
    score = (
        components["store_signal"]
        + components["calibrator_signal"]
        + components["validator_signal"]
        + components["distribution_signal"]
        + components["public_signal"]
        - components["coverage_debt_penalty"]
    )
    return _round(_clamp(score)), components


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Evidence Chain v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- chain_health_score: `{payload.get('chain_health_score')}`",
        f"- chain_completeness_pct: `{payload.get('chain_completeness_pct')}`",
        f"- blocking_step_count: `{payload.get('blocking_step_count')}`",
        "",
        "## Alerts",
        "",
    ]
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    if alerts:
        for alert in alerts:
            lines.append(f"- `{alert}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build end-to-end evidence chain health from replay to benchmark and release")
    parser.add_argument("--replay-observation-store-summary", required=True)
    parser.add_argument("--failure-label-calibrator-summary", required=True)
    parser.add_argument("--mutation-validator-summary", required=True)
    parser.add_argument("--failure-distribution-benchmark-v2-summary", required=True)
    parser.add_argument("--large-coverage-push-v1-summary", default=None)
    parser.add_argument("--anchor-public-release-v1-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_evidence_chain_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    store = _load_json(args.replay_observation_store_summary)
    calibrator = _load_json(args.failure_label_calibrator_summary)
    validator = _load_json(args.mutation_validator_summary)
    benchmark = _load_json(args.failure_distribution_benchmark_v2_summary)
    large_push = _load_json(args.large_coverage_push_v1_summary)
    release = _load_json(args.anchor_public_release_v1_summary)

    reasons: list[str] = []
    if not store:
        reasons.append("replay_observation_store_summary_missing")
    if not calibrator:
        reasons.append("failure_label_calibrator_summary_missing")
    if not validator:
        reasons.append("mutation_validator_summary_missing")
    if not benchmark:
        reasons.append("failure_distribution_benchmark_v2_summary_missing")

    steps = [
        _step_row("replay_observation_store", store, args.replay_observation_store_summary),
        _step_row("failure_label_calibrator", calibrator, args.failure_label_calibrator_summary),
        _step_row("mutation_execution_validator", validator, args.mutation_validator_summary),
        _step_row("failure_distribution_benchmark_v2", benchmark, args.failure_distribution_benchmark_v2_summary),
    ]
    if large_push:
        steps.append(_step_row("large_coverage_push_v1", large_push, args.large_coverage_push_v1_summary))
    if release:
        steps.append(_step_row("anchor_public_release_v1", release, args.anchor_public_release_v1_summary))

    blocking_steps = [x["step_id"] for x in steps if x["state"] == "BLOCKED"]
    warning_steps = [x["step_id"] for x in steps if x["state"] == "ATTN"]

    required_rows = [x for x in steps if x["step_id"] in REQUIRED_STEPS]
    required_ok = len([x for x in required_rows if x["state"] == "OK"])
    completeness = round((required_ok / len(REQUIRED_STEPS)) * 100.0, 2)

    score, score_components = _build_score(store, calibrator, validator, benchmark, release, large_push)
    drift = _to_float(benchmark.get("failure_type_drift", 1.0))

    alerts: list[str] = []
    if blocking_steps:
        alerts.append("blocking_steps_present")
    if warning_steps:
        alerts.append("needs_review_steps_present")
    if drift > 0.35:
        alerts.append("failure_distribution_drift_high")
    if completeness < 100.0:
        alerts.append("required_chain_incomplete")
    if score < 70.0:
        alerts.append("chain_health_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "chain_health_score": score,
        "chain_completeness_pct": completeness,
        "blocking_step_count": len(blocking_steps),
        "warning_step_count": len(warning_steps),
        "blocking_steps": blocking_steps,
        "warning_steps": warning_steps,
        "score_components": score_components,
        "steps": steps,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "replay_observation_store_summary": args.replay_observation_store_summary,
            "failure_label_calibrator_summary": args.failure_label_calibrator_summary,
            "mutation_validator_summary": args.mutation_validator_summary,
            "failure_distribution_benchmark_v2_summary": args.failure_distribution_benchmark_v2_summary,
            "large_coverage_push_v1_summary": args.large_coverage_push_v1_summary,
            "anchor_public_release_v1_summary": args.anchor_public_release_v1_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "chain_health_score": score, "chain_completeness_pct": completeness}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
