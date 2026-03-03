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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Scale Evidence Stamp v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- evidence_score: `{payload.get('evidence_score')}`",
        f"- evidence_grade: `{payload.get('evidence_grade')}`",
        f"- model_file_evidence_ratio: `{payload.get('model_file_evidence_ratio')}`",
        f"- mutation_file_evidence_ratio: `{payload.get('mutation_file_evidence_ratio')}`",
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
    return "D"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build evidence stamp from model/mutation artifact audits")
    parser.add_argument("--real-model-pool-audit-summary", required=True)
    parser.add_argument("--mutation-artifact-inventory-summary", required=True)
    parser.add_argument("--scale-gate-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_scale_evidence_stamp_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    model_audit = _load_json(args.real_model_pool_audit_summary)
    mutation_inventory = _load_json(args.mutation_artifact_inventory_summary)
    scale_gate = _load_json(args.scale_gate_summary)

    reasons: list[str] = []
    if not model_audit:
        reasons.append("real_model_pool_audit_summary_missing")
    if not mutation_inventory:
        reasons.append("mutation_artifact_inventory_summary_missing")

    model_file_ratio = _to_float(model_audit.get("existing_file_ratio", 0.0))
    nontrivial_ratio = _to_float(model_audit.get("nontrivial_model_ratio", 0.0))
    mutation_file_ratio = _to_float(mutation_inventory.get("existing_file_ratio", 0.0))
    execution_coverage_ratio = _to_float(mutation_inventory.get("execution_coverage_ratio", 0.0))
    scale_gate_status = str(scale_gate.get("status") or "UNKNOWN")

    score = 0.0
    score += model_file_ratio * 35.0
    score += nontrivial_ratio * 25.0
    score += mutation_file_ratio * 25.0
    score += execution_coverage_ratio * 10.0
    if scale_gate_status == "PASS":
        score += 5.0
    evidence_score = round(_clamp(score), 2)
    evidence_grade = _grade(evidence_score)

    alerts: list[str] = []
    if model_file_ratio < 0.98:
        alerts.append("model_file_evidence_ratio_low")
    if nontrivial_ratio < 0.7:
        alerts.append("nontrivial_model_ratio_low")
    if mutation_file_ratio < 0.98:
        alerts.append("mutation_file_evidence_ratio_low")
    if execution_coverage_ratio < 0.9:
        alerts.append("execution_coverage_ratio_low")
    if scale_gate_status in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("scale_gate_not_pass")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence_score": evidence_score,
        "evidence_grade": evidence_grade,
        "model_file_evidence_ratio": round(model_file_ratio, 4),
        "nontrivial_model_ratio": round(nontrivial_ratio, 4),
        "mutation_file_evidence_ratio": round(mutation_file_ratio, 4),
        "execution_coverage_ratio": round(execution_coverage_ratio, 4),
        "scale_gate_status": scale_gate_status,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "real_model_pool_audit_summary": args.real_model_pool_audit_summary,
            "mutation_artifact_inventory_summary": args.mutation_artifact_inventory_summary,
            "scale_gate_summary": args.scale_gate_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "evidence_score": evidence_score, "evidence_grade": evidence_grade}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
