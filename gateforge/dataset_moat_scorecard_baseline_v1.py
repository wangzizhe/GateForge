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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> float:
    return round(v, 2)


def _baseline_id(paths: list[str]) -> str:
    digest = hashlib.sha256("|".join(paths).encode("utf-8")).hexdigest()
    return f"moat-baseline-{digest[:12]}"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    indicators = payload.get("indicators") if isinstance(payload.get("indicators"), dict) else {}
    lines = [
        "# GateForge Moat Scorecard Baseline v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- baseline_id: `{payload.get('baseline_id')}`",
        "",
        "## Indicator Snapshot",
        "",
        f"- real_model_count: `{indicators.get('real_model_count')}`",
        f"- reproducible_mutation_count: `{indicators.get('reproducible_mutation_count')}`",
        f"- failure_type_coverage_score: `{indicators.get('failure_type_coverage_score')}`",
        f"- failure_distribution_stability_score: `{indicators.get('failure_distribution_stability_score')}`",
        f"- gateforge_vs_plain_ci_advantage_score: `{indicators.get('gateforge_vs_plain_ci_advantage_score')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed-metric moat scorecard baseline from reproducible artifacts")
    parser.add_argument("--real-model-intake-portfolio-summary", required=True)
    parser.add_argument("--mutation-execution-matrix-summary", required=True)
    parser.add_argument("--failure-distribution-benchmark-summary", required=True)
    parser.add_argument("--gateforge-vs-plain-ci-benchmark-summary", required=True)
    parser.add_argument("--moat-trend-snapshot-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_moat_scorecard_baseline_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    portfolio = _load_json(args.real_model_intake_portfolio_summary)
    matrix = _load_json(args.mutation_execution_matrix_summary)
    benchmark = _load_json(args.failure_distribution_benchmark_summary)
    compare = _load_json(args.gateforge_vs_plain_ci_benchmark_summary)
    moat = _load_json(args.moat_trend_snapshot_summary)

    reasons: list[str] = []
    if not portfolio:
        reasons.append("real_model_intake_portfolio_summary_missing")
    if not matrix:
        reasons.append("mutation_execution_matrix_summary_missing")
    if not benchmark:
        reasons.append("failure_distribution_benchmark_summary_missing")
    if not compare:
        reasons.append("gateforge_vs_plain_ci_benchmark_summary_missing")

    real_model_count = _to_int(portfolio.get("total_real_models", 0))
    reproducible_mutation_count = _to_int(matrix.get("matrix_cell_count", 0))
    failure_type_drift = _to_float(benchmark.get("failure_type_drift", 0.0))
    model_scale_drift = _to_float(benchmark.get("model_scale_drift", 0.0))
    failure_type_coverage_score = _round(_clamp(100.0 - (failure_type_drift * 100.0)))
    failure_distribution_stability_score = _round(_clamp(100.0 - (((failure_type_drift + model_scale_drift) / 2.0) * 100.0)))
    gateforge_advantage_score = _to_int(compare.get("advantage_score", 0))
    moat_score = _to_float(moat.get("moat_score", 0.0))

    indicators = {
        "real_model_count": real_model_count,
        "reproducible_mutation_count": reproducible_mutation_count,
        "failure_type_coverage_score": failure_type_coverage_score,
        "failure_distribution_stability_score": failure_distribution_stability_score,
        "gateforge_vs_plain_ci_advantage_score": gateforge_advantage_score,
        "moat_score": _round(moat_score),
    }

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif real_model_count < 1 or reproducible_mutation_count < 1:
        status = "NEEDS_REVIEW"

    source_paths = [
        args.real_model_intake_portfolio_summary,
        args.mutation_execution_matrix_summary,
        args.failure_distribution_benchmark_summary,
        args.gateforge_vs_plain_ci_benchmark_summary,
        args.moat_trend_snapshot_summary or "",
    ]

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "baseline_id": _baseline_id(source_paths),
        "version": "v1",
        "indicators": indicators,
        "measurement_contract": {
            "real_model_count": "portfolio.total_real_models",
            "reproducible_mutation_count": "mutation_matrix.matrix_cell_count",
            "failure_type_coverage_score": "100 - failure_type_drift*100",
            "failure_distribution_stability_score": "100 - average(failure_type_drift, model_scale_drift)*100",
            "gateforge_vs_plain_ci_advantage_score": "compare.advantage_score",
        },
        "sources": {
            "real_model_intake_portfolio_summary": args.real_model_intake_portfolio_summary,
            "mutation_execution_matrix_summary": args.mutation_execution_matrix_summary,
            "failure_distribution_benchmark_summary": args.failure_distribution_benchmark_summary,
            "gateforge_vs_plain_ci_benchmark_summary": args.gateforge_vs_plain_ci_benchmark_summary,
            "moat_trend_snapshot_summary": args.moat_trend_snapshot_summary,
        },
        "reasons": sorted(set(reasons)),
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "baseline_id": payload.get("baseline_id")}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
