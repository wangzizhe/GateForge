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


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _status(v: dict) -> str:
    return str(v.get("status") or "UNKNOWN")


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Evidence Release Manifest",
        "",
        f"- status: `{payload.get('status')}`",
        f"- release_ready: `{payload.get('release_ready')}`",
        f"- artifact_count: `{payload.get('artifact_count')}`",
        f"- target_gap_pressure_index: `{payload.get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{payload.get('model_asset_target_gap_score')}`",
        "",
        "## Artifacts",
        "",
    ]
    for row in payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []:
        lines.append(f"- `{row.get('name')}` status=`{row.get('status')}` role=`{row.get('role')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create release manifest for externally shareable governance evidence")
    parser.add_argument("--governance-decision-proofbook", required=True)
    parser.add_argument("--moat-execution-forecast", required=True)
    parser.add_argument("--model-scale-mix-guard", required=True)
    parser.add_argument("--failure-supply-plan", required=True)
    parser.add_argument("--out", default="artifacts/dataset_governance_evidence_release_manifest/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    proofbook = _load_json(args.governance_decision_proofbook)
    forecast = _load_json(args.moat_execution_forecast)
    mix_guard = _load_json(args.model_scale_mix_guard)
    supply = _load_json(args.failure_supply_plan)

    reasons: list[str] = []
    if not proofbook:
        reasons.append("proofbook_missing")
    if not forecast:
        reasons.append("forecast_missing")
    if not mix_guard:
        reasons.append("mix_guard_missing")
    if not supply:
        reasons.append("supply_plan_missing")

    artifacts = [
        {"name": "governance_decision_proofbook", "status": _status(proofbook), "role": "decision_trace"},
        {"name": "moat_execution_forecast", "status": _status(forecast), "role": "forward_outlook"},
        {"name": "model_scale_mix_guard", "status": _status(mix_guard), "role": "coverage_balance_guardrail"},
        {"name": "failure_supply_plan", "status": _status(supply), "role": "execution_supply_plan"},
    ]

    fail_count = len([a for a in artifacts if a["status"] == "FAIL"])
    pass_count = len([a for a in artifacts if a["status"] == "PASS"])
    target_gap_pressure = _to_float(forecast.get("target_gap_pressure_index", 0.0))
    target_gap_score = _to_float(forecast.get("model_asset_target_gap_score", 0.0))

    release_ready = False
    status = "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"
    elif fail_count == 0 and pass_count >= 2:
        release_ready = True
        status = "PASS"

    if status != "FAIL" and target_gap_pressure and target_gap_pressure < 70.0:
        status = "NEEDS_REVIEW"
        release_ready = False
        reasons.append("target_gap_pressure_low")
    if status != "FAIL" and target_gap_score >= 25.0:
        status = "NEEDS_REVIEW"
        release_ready = False
        reasons.append("model_asset_target_gap_high")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "release_ready": release_ready,
        "artifact_count": len(artifacts),
        "target_gap_pressure_index": round(target_gap_pressure, 2),
        "model_asset_target_gap_score": round(target_gap_score, 2),
        "artifacts": artifacts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "governance_decision_proofbook": args.governance_decision_proofbook,
            "moat_execution_forecast": args.moat_execution_forecast,
            "model_scale_mix_guard": args.model_scale_mix_guard,
            "failure_supply_plan": args.failure_supply_plan,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "release_ready": release_ready, "artifact_count": len(artifacts)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
