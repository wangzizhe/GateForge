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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _execution_score(exec_auth: dict) -> float:
    solver_ratio = _clamp(_to_float(exec_auth.get("solver_command_ratio_pct", 0.0)), 0.0, 100.0)
    probe_ratio = _clamp(_to_float(exec_auth.get("probe_only_command_ratio_pct", 100.0)), 0.0, 100.0)
    failure_signal_ratio = _clamp(_to_float(exec_auth.get("failure_signal_ratio_pct", 0.0)), 0.0, 100.0)
    score = solver_ratio * 0.55 + (100.0 - probe_ratio) * 0.25 + failure_signal_ratio * 0.20
    return round(_clamp(score, 0.0, 100.0), 2)


def _failure_signal_score(failure_auth: dict) -> float:
    failure_ratio = _clamp(_to_float(failure_auth.get("failure_signal_ratio_pct", 0.0)), 0.0, 100.0)
    expected_cov = _clamp(_to_float(failure_auth.get("expected_failure_type_signal_coverage_pct", 0.0)), 0.0, 100.0)
    observed_cov = _clamp(_to_float(failure_auth.get("observed_coverage_ratio_pct", 0.0)), 0.0, 100.0)
    score = failure_ratio * 0.50 + expected_cov * 0.35 + observed_cov * 0.15
    return round(_clamp(score, 0.0, 100.0), 2)


def _effective_depth_score(depth: dict) -> float:
    ratio = _clamp(_to_float(depth.get("models_meeting_effective_depth_ratio_pct", 0.0)), 0.0, 100.0)
    large_ratio = _clamp(_to_float(depth.get("large_models_meeting_effective_depth_ratio_pct", 0.0)), 0.0, 100.0)
    p10 = _clamp(_to_float(depth.get("p10_effective_mutations_per_model", 0.0)) * 20.0, 0.0, 100.0)
    score = ratio * 0.45 + large_ratio * 0.35 + p10 * 0.20
    return round(_clamp(score, 0.0, 100.0), 2)


def _source_provenance_score(source: dict) -> float:
    existing_ratio = _clamp(_to_float(source.get("existing_source_path_ratio_pct", 0.0)), 0.0, 100.0)
    allowed_ratio = _clamp(_to_float(source.get("allowed_root_ratio_pct", 0.0)), 0.0, 100.0)
    registry_ratio = _clamp(_to_float(source.get("registry_match_ratio_pct", 0.0)), 0.0, 100.0)
    score = existing_ratio * 0.40 + allowed_ratio * 0.30 + registry_ratio * 0.30
    return round(_clamp(score, 0.0, 100.0), 2)


def _effective_scale_score(scale: dict) -> float:
    ratio = _clamp(_to_float(scale.get("effective_vs_generated_ratio_pct", 0.0)), 0.0, 100.0)
    mult = _clamp(_to_float(scale.get("authenticity_multiplier", 0.0)) * 100.0, 0.0, 100.0)
    score = ratio * 0.65 + mult * 0.35
    return round(_clamp(score, 0.0, 100.0), 2)


def _grade(score: float) -> str:
    if score >= 90.0:
        return "A"
    if score >= 80.0:
        return "B"
    if score >= 70.0:
        return "C"
    if score >= 60.0:
        return "D"
    return "F"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Authentic Scale Score v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- authentic_scale_score: `{payload.get('authentic_scale_score')}`",
        f"- authentic_scale_grade: `{payload.get('authentic_scale_grade')}`",
        f"- warning_count: `{payload.get('warning_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute unified mutation authenticity scale score from execution/failure/depth/source signals")
    parser.add_argument("--mutation-execution-authenticity-summary", required=True)
    parser.add_argument("--mutation-failure-signal-authenticity-summary", required=True)
    parser.add_argument("--mutation-effective-depth-summary", required=True)
    parser.add_argument("--mutation-source-provenance-summary", required=True)
    parser.add_argument("--mutation-effective-scale-summary", default=None)
    parser.add_argument("--min-score-pass", type=float, default=70.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_authentic_scale_score_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    exec_auth = _load_json(args.mutation_execution_authenticity_summary)
    failure_auth = _load_json(args.mutation_failure_signal_authenticity_summary)
    depth = _load_json(args.mutation_effective_depth_summary)
    source = _load_json(args.mutation_source_provenance_summary)
    effective_scale = _load_json(args.mutation_effective_scale_summary)

    reasons: list[str] = []
    if not exec_auth:
        reasons.append("mutation_execution_authenticity_summary_missing")
    if not failure_auth:
        reasons.append("mutation_failure_signal_authenticity_summary_missing")
    if not depth:
        reasons.append("mutation_effective_depth_summary_missing")
    if not source:
        reasons.append("mutation_source_provenance_summary_missing")

    component_scores = {
        "execution_authenticity_score": _execution_score(exec_auth),
        "failure_signal_authenticity_score": _failure_signal_score(failure_auth),
        "effective_depth_authenticity_score": _effective_depth_score(depth),
        "source_provenance_authenticity_score": _source_provenance_score(source),
        "effective_scale_authenticity_score": _effective_scale_score(effective_scale) if effective_scale else None,
    }
    weighted_items = [
        ("execution_authenticity_score", 0.35),
        ("failure_signal_authenticity_score", 0.25),
        ("effective_depth_authenticity_score", 0.25),
        ("source_provenance_authenticity_score", 0.15),
    ]
    if effective_scale:
        weighted_items.append(("effective_scale_authenticity_score", 0.10))
        weighted_items = [(k, w * 0.90) for (k, w) in weighted_items[:-1]] + [weighted_items[-1]]

    weighted_sum = 0.0
    total_weight = 0.0
    for key, weight in weighted_items:
        val = component_scores.get(key)
        if isinstance(val, (int, float)):
            weighted_sum += float(val) * weight
            total_weight += weight
    authentic_scale_score = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0
    authentic_scale_grade = _grade(authentic_scale_score)

    warning_reasons: list[str] = []
    if str(exec_auth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("execution_authenticity_not_pass")
    if str(failure_auth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("failure_signal_authenticity_not_pass")
    if str(depth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("effective_depth_not_pass")
    if str(source.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("source_provenance_not_pass")
    if effective_scale and str(effective_scale.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("effective_scale_not_pass")
    if authentic_scale_score < float(args.min_score_pass):
        warning_reasons.append("authentic_scale_score_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif warning_reasons:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "authentic_scale_score": authentic_scale_score,
        "authentic_scale_grade": authentic_scale_grade,
        "component_scores": component_scores,
        "warning_count": len(warning_reasons),
        "warning_reasons": warning_reasons,
        "thresholds": {"min_score_pass": float(args.min_score_pass)},
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_execution_authenticity_summary": args.mutation_execution_authenticity_summary,
            "mutation_failure_signal_authenticity_summary": args.mutation_failure_signal_authenticity_summary,
            "mutation_effective_depth_summary": args.mutation_effective_depth_summary,
            "mutation_source_provenance_summary": args.mutation_source_provenance_summary,
            "mutation_effective_scale_summary": args.mutation_effective_scale_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "authentic_scale_score": authentic_scale_score,
                "authentic_scale_grade": authentic_scale_grade,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
