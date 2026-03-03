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

    weighted = (
        family_score * 0.12
        + source_score * 0.14
        + repro_score * 0.22
        + large_truth_score * 0.22
        + growth_auth_score * 0.14
        + hard_moat_score * 0.16
    )
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
