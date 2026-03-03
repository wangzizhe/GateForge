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


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _authenticity_score(auth: dict) -> float:
    if not auth:
        return 0.0
    solver_ratio = _clamp(_to_float(auth.get("solver_command_ratio_pct", 0.0)), 0.0, 100.0)
    probe_ratio = _clamp(_to_float(auth.get("probe_only_command_ratio_pct", 100.0)), 0.0, 100.0)
    failure_signal = _clamp(_to_float(auth.get("failure_signal_ratio_pct", 0.0)), 0.0, 100.0)
    score = solver_ratio * 0.5 + (100.0 - probe_ratio) * 0.3 + failure_signal * 0.2
    return round(_clamp(score, 0.0, 100.0), 2)


def _failure_signal_authenticity_score(failure_auth: dict) -> float:
    if not failure_auth:
        return 0.0
    failure_ratio = _clamp(_to_float(failure_auth.get("failure_signal_ratio_pct", 0.0)), 0.0, 100.0)
    type_cov = _clamp(_to_float(failure_auth.get("expected_failure_type_signal_coverage_pct", 0.0)), 0.0, 100.0)
    observed_cov = _clamp(_to_float(failure_auth.get("observed_coverage_ratio_pct", 0.0)), 0.0, 100.0)
    score = failure_ratio * 0.5 + type_cov * 0.4 + observed_cov * 0.1
    return round(_clamp(score, 0.0, 100.0), 2)


def _effective_depth_score(depth: dict) -> float:
    if not depth:
        return 0.0
    ratio = _clamp(_to_float(depth.get("models_meeting_effective_depth_ratio_pct", 0.0)), 0.0, 100.0)
    large_ratio = _clamp(_to_float(depth.get("large_models_meeting_effective_depth_ratio_pct", 0.0)), 0.0, 100.0)
    p10 = _clamp(_to_float(depth.get("p10_effective_mutations_per_model", 0.0)) * 20.0, 0.0, 100.0)
    score = ratio * 0.5 + large_ratio * 0.3 + p10 * 0.2
    return round(_clamp(score, 0.0, 100.0), 2)


def _source_provenance_score(source_prov: dict) -> float:
    if not source_prov:
        return 0.0
    existing_ratio = _clamp(_to_float(source_prov.get("existing_source_path_ratio_pct", 0.0)), 0.0, 100.0)
    allowed_ratio = _clamp(_to_float(source_prov.get("allowed_root_ratio_pct", 0.0)), 0.0, 100.0)
    registry_ratio = _clamp(_to_float(source_prov.get("registry_match_ratio_pct", 0.0)), 0.0, 100.0)
    score = existing_ratio * 0.45 + allowed_ratio * 0.35 + registry_ratio * 0.2
    return round(_clamp(score, 0.0, 100.0), 2)


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Joint Moat Strength Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_strength_score: `{payload.get('moat_strength_score')}`",
        f"- moat_strength_grade: `{payload.get('moat_strength_grade')}`",
        f"- hard_fail_count: `{payload.get('hard_fail_count')}`",
        f"- warning_count: `{payload.get('warning_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified moat strength gate from core model/mutation quality pillars")
    parser.add_argument("--real-model-family-coverage-summary", required=True)
    parser.add_argument("--real-model-source-diversity-summary", required=True)
    parser.add_argument("--mutation-repro-depth-summary", required=True)
    parser.add_argument("--large-model-executable-truth-summary", required=True)
    parser.add_argument("--real-model-net-growth-authenticity-summary", required=True)
    parser.add_argument("--hard-moat-gates-summary", required=True)
    parser.add_argument("--mutation-execution-authenticity-summary", default=None)
    parser.add_argument("--mutation-failure-signal-authenticity-summary", default=None)
    parser.add_argument("--mutation-effective-depth-summary", default=None)
    parser.add_argument("--mutation-source-provenance-summary", default=None)
    parser.add_argument("--min-score-pass", type=float, default=78.0)
    parser.add_argument("--out", default="artifacts/dataset_joint_moat_strength_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    family = _load_json(args.real_model_family_coverage_summary)
    source = _load_json(args.real_model_source_diversity_summary)
    repro = _load_json(args.mutation_repro_depth_summary)
    large_truth = _load_json(args.large_model_executable_truth_summary)
    net_growth = _load_json(args.real_model_net_growth_authenticity_summary)
    hard_moat = _load_json(args.hard_moat_gates_summary)
    exec_auth = _load_json(args.mutation_execution_authenticity_summary)
    failure_auth = _load_json(args.mutation_failure_signal_authenticity_summary)
    effective_depth = _load_json(args.mutation_effective_depth_summary)
    source_prov = _load_json(args.mutation_source_provenance_summary)

    reasons: list[str] = []
    if not family:
        reasons.append("real_model_family_coverage_summary_missing")
    if not source:
        reasons.append("real_model_source_diversity_summary_missing")
    if not repro:
        reasons.append("mutation_repro_depth_summary_missing")
    if not large_truth:
        reasons.append("large_model_executable_truth_summary_missing")
    if not net_growth:
        reasons.append("real_model_net_growth_authenticity_summary_missing")
    if not hard_moat:
        reasons.append("hard_moat_gates_summary_missing")

    family_score = _clamp(_to_float(family.get("family_entropy", 0.0)) * 50.0, 0.0, 100.0)
    source_score = _clamp(100.0 - _to_float(source.get("max_source_bucket_share_pct", 100.0)), 0.0, 100.0)
    repro_score = _clamp(_to_float(repro.get("models_meeting_depth_ratio_pct", 0.0)), 0.0, 100.0)
    large_truth_score = _clamp(_to_float(large_truth.get("large_executable_real_rate_pct", 0.0)), 0.0, 100.0)
    growth_auth_score = _clamp(_to_float(net_growth.get("true_growth_ratio_pct", 0.0)), 0.0, 100.0)
    hard_moat_score = _clamp(_to_float(hard_moat.get("moat_hardness_score", 0.0)), 0.0, 100.0)
    exec_auth_score = _authenticity_score(exec_auth)
    failure_auth_score = _failure_signal_authenticity_score(failure_auth)
    effective_depth_score = _effective_depth_score(effective_depth)
    source_prov_score = _source_provenance_score(source_prov)

    base_weighted = (
        family_score * 0.12
        + source_score * 0.14
        + repro_score * 0.22
        + large_truth_score * 0.22
        + growth_auth_score * 0.14
        + hard_moat_score * 0.16
    )
    weighted = base_weighted
    optional_scores: list[float] = []
    if exec_auth:
        optional_scores.append(exec_auth_score)
    if failure_auth:
        optional_scores.append(failure_auth_score)
    if effective_depth:
        optional_scores.append(effective_depth_score)
    if source_prov:
        optional_scores.append(source_prov_score)
    if optional_scores:
        optional_avg = sum(optional_scores) / max(1, len(optional_scores))
        weighted = base_weighted * 0.85 + optional_avg * 0.15
    moat_strength_score = round(weighted, 2)
    moat_strength_grade = _grade(moat_strength_score)

    hard_fail_reasons: list[str] = []
    warning_reasons: list[str] = []

    if str(hard_moat.get("status") or "") == "FAIL":
        hard_fail_reasons.append("hard_moat_gates_fail")
    if str(large_truth.get("status") or "") == "FAIL":
        hard_fail_reasons.append("large_model_executable_truth_fail")
    if str(net_growth.get("status") or "") == "FAIL":
        hard_fail_reasons.append("net_growth_authenticity_fail")

    if str(family.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("family_coverage_not_pass")
    if str(source.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("source_diversity_not_pass")
    if str(repro.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("repro_depth_not_pass")
    if str(large_truth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("large_model_truth_not_pass")
    if str(net_growth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("net_growth_auth_not_pass")
    if exec_auth and str(exec_auth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("mutation_execution_authenticity_not_pass")
    if exec_auth and exec_auth_score < 30.0:
        warning_reasons.append("mutation_execution_authenticity_score_low")
    if failure_auth and str(failure_auth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("mutation_failure_signal_authenticity_not_pass")
    if failure_auth and failure_auth_score < 30.0:
        warning_reasons.append("mutation_failure_signal_authenticity_score_low")
    if effective_depth and str(effective_depth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("mutation_effective_depth_not_pass")
    if effective_depth and effective_depth_score < 30.0:
        warning_reasons.append("mutation_effective_depth_score_low")
    if source_prov and str(source_prov.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        warning_reasons.append("mutation_source_provenance_not_pass")
    if source_prov and source_prov_score < 30.0:
        warning_reasons.append("mutation_source_provenance_score_low")
    if moat_strength_score < float(args.min_score_pass):
        warning_reasons.append("joint_moat_strength_score_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif hard_fail_reasons:
        status = "FAIL"
    elif warning_reasons:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "moat_strength_score": moat_strength_score,
        "moat_strength_grade": moat_strength_grade,
        "hard_fail_count": len(hard_fail_reasons),
        "warning_count": len(warning_reasons),
        "hard_fail_reasons": hard_fail_reasons,
        "warning_reasons": warning_reasons,
        "component_scores": {
            "family_score": round(family_score, 2),
            "source_score": round(source_score, 2),
            "repro_score": round(repro_score, 2),
            "large_truth_score": round(large_truth_score, 2),
            "growth_auth_score": round(growth_auth_score, 2),
            "hard_moat_score": round(hard_moat_score, 2),
            "mutation_execution_authenticity_score": round(exec_auth_score, 2),
            "mutation_failure_signal_authenticity_score": round(failure_auth_score, 2),
            "mutation_effective_depth_score": round(effective_depth_score, 2),
            "mutation_source_provenance_score": round(source_prov_score, 2),
        },
        "alerts": warning_reasons,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_family_coverage_summary": args.real_model_family_coverage_summary,
            "real_model_source_diversity_summary": args.real_model_source_diversity_summary,
            "mutation_repro_depth_summary": args.mutation_repro_depth_summary,
            "large_model_executable_truth_summary": args.large_model_executable_truth_summary,
            "real_model_net_growth_authenticity_summary": args.real_model_net_growth_authenticity_summary,
            "hard_moat_gates_summary": args.hard_moat_gates_summary,
            "mutation_execution_authenticity_summary": args.mutation_execution_authenticity_summary,
            "mutation_failure_signal_authenticity_summary": args.mutation_failure_signal_authenticity_summary,
            "mutation_effective_depth_summary": args.mutation_effective_depth_summary,
            "mutation_source_provenance_summary": args.mutation_source_provenance_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "moat_strength_score": moat_strength_score,
                "moat_strength_grade": moat_strength_grade,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
