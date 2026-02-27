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


def _score_status(status: str) -> float:
    if status == "PASS":
        return 100.0
    if status == "NEEDS_REVIEW":
        return 60.0
    if status == "FAIL":
        return 0.0
    return 40.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Moat Readiness Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- moat_readiness_score: `{payload.get('moat_readiness_score')}`",
        f"- release_recommendation: `{payload.get('release_recommendation')}`",
        f"- blocking_signal_count: `{payload.get('blocking_signal_count')}`",
        f"- confidence_level: `{payload.get('confidence_level')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate Modelica moat readiness based on intake, mutation, and backlog signals")
    parser.add_argument("--real-model-license-compliance-summary", required=True)
    parser.add_argument("--modelica-mutation-recipe-library-summary", required=True)
    parser.add_argument("--real-model-failure-yield-summary", required=True)
    parser.add_argument("--real-model-intake-backlog-summary", required=True)
    parser.add_argument("--external-proof-score-summary", default=None)
    parser.add_argument("--min-moat-readiness-score", type=float, default=78.0)
    parser.add_argument("--out", default="artifacts/dataset_modelica_moat_readiness_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    license_summary = _load_json(args.real_model_license_compliance_summary)
    recipe_summary = _load_json(args.modelica_mutation_recipe_library_summary)
    yield_summary = _load_json(args.real_model_failure_yield_summary)
    backlog_summary = _load_json(args.real_model_intake_backlog_summary)
    external_proof = _load_json(args.external_proof_score_summary)

    reasons: list[str] = []
    if not license_summary:
        reasons.append("real_model_license_compliance_summary_missing")
    if not recipe_summary:
        reasons.append("modelica_mutation_recipe_library_summary_missing")
    if not yield_summary:
        reasons.append("real_model_failure_yield_summary_missing")
    if not backlog_summary:
        reasons.append("real_model_intake_backlog_summary_missing")

    license_score = _score_status(str(license_summary.get("status") or ""))
    recipe_score = _score_status(str(recipe_summary.get("status") or ""))
    yield_score = _score_status(str(yield_summary.get("status") or ""))

    p0_count = int(backlog_summary.get("p0_count", 0) or 0)
    backlog_score = max(0.0, 100.0 - min(80.0, p0_count * 15.0))

    external_score = float(external_proof.get("external_proof_score", 70.0) or 70.0)

    moat_score = round(
        (license_score * 0.25)
        + (recipe_score * 0.2)
        + (yield_score * 0.3)
        + (backlog_score * 0.15)
        + (external_score * 0.1),
        2,
    )

    blocking_signals: list[str] = []
    if str(license_summary.get("status") or "") == "FAIL":
        blocking_signals.append("license_compliance_fail")
    if str(yield_summary.get("status") or "") == "FAIL":
        blocking_signals.append("failure_yield_fail")
    if p0_count >= 4:
        blocking_signals.append("p0_backlog_too_high")
    if moat_score < float(args.min_moat_readiness_score):
        blocking_signals.append("moat_readiness_score_below_threshold")
    if float(license_summary.get("license_risk_score", 0.0) or 0.0) >= 30.0:
        blocking_signals.append("license_risk_score_high")

    alerts: list[str] = []
    if p0_count > 0:
        alerts.append("p0_backlog_present")
    if str(recipe_summary.get("status") or "") != "PASS":
        alerts.append("recipe_library_not_pass")
    if float(yield_summary.get("effective_yield_score", 0.0) or 0.0) < 55.0:
        alerts.append("effective_yield_score_low")

    release_recommendation = "HOLD"
    if not blocking_signals and str(yield_summary.get("status") or "") == "PASS":
        release_recommendation = "GO"
    elif moat_score >= float(args.min_moat_readiness_score):
        release_recommendation = "LIMITED_GO"
    confidence_level = "low"
    if moat_score >= 85.0 and len(blocking_signals) == 0:
        confidence_level = "high"
    elif moat_score >= 70.0:
        confidence_level = "medium"
    critical_blockers = [x for x in blocking_signals if x in {"license_compliance_fail", "failure_yield_fail", "license_risk_score_high"}]

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif blocking_signals or alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "moat_readiness_score": moat_score,
        "release_recommendation": release_recommendation,
        "blocking_signal_count": len(blocking_signals),
        "blocking_signals": blocking_signals,
        "critical_blockers": critical_blockers,
        "confidence_level": confidence_level,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "component_scores": {
            "license_score": license_score,
            "recipe_score": recipe_score,
            "yield_score": yield_score,
            "backlog_score": backlog_score,
            "external_proof_score": external_score,
        },
        "sources": {
            "real_model_license_compliance_summary": args.real_model_license_compliance_summary,
            "modelica_mutation_recipe_library_summary": args.modelica_mutation_recipe_library_summary,
            "real_model_failure_yield_summary": args.real_model_failure_yield_summary,
            "real_model_intake_backlog_summary": args.real_model_intake_backlog_summary,
            "external_proof_score_summary": args.external_proof_score_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "moat_readiness_score": moat_score, "release_recommendation": release_recommendation}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
