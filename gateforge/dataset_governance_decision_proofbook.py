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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Governance Decision Proofbook",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- confidence: `{payload.get('confidence')}`",
        "",
        "## Evidence Cards",
        "",
    ]
    for card in payload.get("evidence_cards") if isinstance(payload.get("evidence_cards"), list) else []:
        lines.append(f"- `{card.get('name')}` status=`{card.get('status')}` signal=`{card.get('signal')}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build concise governance proofbook from key evidence artifacts")
    parser.add_argument("--governance-evidence-pack", required=True)
    parser.add_argument("--moat-execution-forecast", required=True)
    parser.add_argument("--pack-execution-tracker", required=True)
    parser.add_argument("--policy-experiment-runner", required=True)
    parser.add_argument("--out", default="artifacts/dataset_governance_decision_proofbook/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    evidence = _load_json(args.governance_evidence_pack)
    forecast = _load_json(args.moat_execution_forecast)
    tracker = _load_json(args.pack_execution_tracker)
    experiments = _load_json(args.policy_experiment_runner)

    reasons: list[str] = []
    if not evidence:
        reasons.append("governance_evidence_pack_missing")
    if not forecast:
        reasons.append("moat_execution_forecast_missing")
    if not tracker:
        reasons.append("pack_execution_tracker_missing")
    if not experiments:
        reasons.append("policy_experiment_runner_missing")

    cards = [
        {"name": "evidence_pack", "status": _status(evidence), "signal": str(evidence.get("status") or "")},
        {"name": "execution_forecast", "status": _status(forecast), "signal": str(forecast.get("recommendation") or "")},
        {"name": "execution_tracker", "status": _status(tracker), "signal": str(tracker.get("progress_percent") or "")},
        {"name": "policy_experiments", "status": _status(experiments), "signal": str(experiments.get("recommendation") or "")},
    ]

    pass_count = len([c for c in cards if c["status"] == "PASS"])
    fail_count = len([c for c in cards if c["status"] == "FAIL"])

    decision = "PROMOTE_WITH_GUARDS"
    confidence = "medium"
    status = "NEEDS_REVIEW"

    if fail_count > 0 or reasons:
        decision = "HOLD"
        confidence = "low"
        status = "FAIL" if reasons else "NEEDS_REVIEW"
    elif pass_count >= 3:
        decision = "PROMOTE"
        confidence = "high"
        status = "PASS"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "confidence": confidence,
        "evidence_cards": cards,
        "reasons": sorted(set(reasons)),
        "sources": {
            "governance_evidence_pack": args.governance_evidence_pack,
            "moat_execution_forecast": args.moat_execution_forecast,
            "pack_execution_tracker": args.pack_execution_tracker,
            "policy_experiment_runner": args.policy_experiment_runner,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "decision": decision, "confidence": confidence}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
