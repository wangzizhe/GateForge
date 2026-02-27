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


def _status(v: object) -> str:
    return str(v or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modelica Release Candidate Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- release_candidate_score: `{payload.get('release_candidate_score')}`",
        f"- candidate_decision: `{payload.get('candidate_decision')}`",
        f"- blocking_signals: `{len(payload.get('blocking_signals') or [])}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate release candidate readiness for Modelica moat chain")
    parser.add_argument("--real-model-supply-health-summary", required=True)
    parser.add_argument("--mutation-recipe-execution-audit-summary", required=True)
    parser.add_argument("--modelica-moat-readiness-gate-summary", required=True)
    parser.add_argument("--min-release-candidate-score", type=float, default=80.0)
    parser.add_argument("--out", default="artifacts/dataset_modelica_release_candidate_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    supply = _load_json(args.real_model_supply_health_summary)
    audit = _load_json(args.mutation_recipe_execution_audit_summary)
    moat = _load_json(args.modelica_moat_readiness_gate_summary)

    reasons: list[str] = []
    if not supply:
        reasons.append("real_model_supply_health_summary_missing")
    if not audit:
        reasons.append("mutation_recipe_execution_audit_summary_missing")
    if not moat:
        reasons.append("modelica_moat_readiness_gate_summary_missing")

    supply_score = _to_float(supply.get("supply_health_score", 0.0))
    audit_score = _to_float(audit.get("execution_coverage_pct", 0.0))
    moat_score = _to_float(moat.get("moat_readiness_score", 0.0))

    release_candidate_score = round((supply_score * 0.4) + (audit_score * 0.25) + (moat_score * 0.35), 2)

    blocking_signals: list[str] = []
    if _status(supply.get("status")) == "FAIL":
        blocking_signals.append("supply_health_fail")
    if _status(audit.get("status")) == "FAIL":
        blocking_signals.append("recipe_execution_audit_fail")
    if _status(moat.get("status")) == "FAIL":
        blocking_signals.append("moat_readiness_fail")
    if int(supply.get("supply_gap_count", 0) or 0) >= 2:
        blocking_signals.append("supply_gaps_high")
    if int(audit.get("missing_recipe_count", 0) or 0) >= 4:
        blocking_signals.append("missing_recipe_count_high")
    if release_candidate_score < float(args.min_release_candidate_score):
        blocking_signals.append("release_candidate_score_below_threshold")

    candidate_decision = "GO"
    if blocking_signals:
        candidate_decision = "HOLD"
    elif _status(supply.get("status")) == "NEEDS_REVIEW" or _status(audit.get("status")) == "NEEDS_REVIEW":
        candidate_decision = "LIMITED_GO"

    alerts: list[str] = []
    if _status(moat.get("status")) != "PASS":
        alerts.append("moat_not_pass")
    if _status(audit.get("status")) != "PASS":
        alerts.append("recipe_audit_not_pass")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif blocking_signals or alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "release_candidate_score": release_candidate_score,
        "candidate_decision": candidate_decision,
        "blocking_signals": blocking_signals,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "score_breakdown": {
            "supply_health_score": supply_score,
            "recipe_execution_coverage_pct": audit_score,
            "moat_readiness_score": moat_score,
        },
        "sources": {
            "real_model_supply_health_summary": args.real_model_supply_health_summary,
            "mutation_recipe_execution_audit_summary": args.mutation_recipe_execution_audit_summary,
            "modelica_moat_readiness_gate_summary": args.modelica_moat_readiness_gate_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "candidate_decision": candidate_decision, "release_candidate_score": release_candidate_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
