from __future__ import annotations

import argparse
import json
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Milestone Public Brief v1",
        "",
        f"- milestone_status: `{payload.get('milestone_status')}`",
        f"- milestone_decision: `{payload.get('milestone_decision')}`",
        f"- checkpoint_score: `{payload.get('checkpoint_score')}`",
        f"- moat_public_score: `{payload.get('moat_public_score')}`",
        f"- alignment_score: `{payload.get('alignment_score')}`",
        f"- model_asset_momentum_status: `{payload.get('model_asset_momentum_status')}`",
        f"- model_asset_momentum_score: `{payload.get('model_asset_momentum_score')}`",
        f"- delta_total_real_models: `{payload.get('delta_total_real_models')}`",
        f"- delta_large_models: `{payload.get('delta_large_models')}`",
        f"- target_gap_pressure_index: `{payload.get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{payload.get('model_asset_target_gap_score')}`",
        f"- target_gap_supply_pressure_index: `{payload.get('target_gap_supply_pressure_index')}`",
        f"- target_gap_narrative_status: `{payload.get('target_gap_narrative_status')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build concise public-facing milestone brief")
    parser.add_argument("--milestone-checkpoint-summary", required=True)
    parser.add_argument("--moat-public-scoreboard-summary", required=True)
    parser.add_argument("--snapshot-moat-alignment-summary", required=True)
    parser.add_argument("--governance-decision-proofbook-summary", default=None)
    parser.add_argument("--failure-supply-plan-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_milestone_public_brief_v1/brief.json")
    parser.add_argument("--report-out", default="artifacts/dataset_milestone_public_brief_v1/brief.md")
    args = parser.parse_args()

    checkpoint = _load_json(args.milestone_checkpoint_summary)
    scoreboard = _load_json(args.moat_public_scoreboard_summary)
    alignment = _load_json(args.snapshot_moat_alignment_summary)
    proofbook = _load_json(args.governance_decision_proofbook_summary)
    supply_plan = _load_json(args.failure_supply_plan_summary)

    target_gap_pressure = proofbook.get("target_gap_pressure_index")
    target_gap_score = proofbook.get("model_asset_target_gap_score")
    target_gap_band = proofbook.get("target_gap_band")
    target_gap_supply_pressure = supply_plan.get("target_gap_supply_pressure_index")
    target_gap_narrative_status = "PASS"
    if str(proofbook.get("status") or "") == "FAIL" or str(supply_plan.get("status") or "") == "FAIL":
        target_gap_narrative_status = "FAIL"
    elif (
        (isinstance(target_gap_score, (int, float)) and float(target_gap_score) >= 35.0)
        or (isinstance(target_gap_pressure, (int, float)) and float(target_gap_pressure) < 60.0)
        or (isinstance(target_gap_supply_pressure, (int, float)) and float(target_gap_supply_pressure) >= 65.0)
    ):
        target_gap_narrative_status = "NEEDS_REVIEW"

    key_risks = checkpoint.get("blockers") or checkpoint.get("alerts") or []
    if not isinstance(key_risks, list):
        key_risks = []
    if target_gap_narrative_status == "NEEDS_REVIEW":
        key_risks.append("target_gap_signal_requires_gap_closure")
    if target_gap_narrative_status == "FAIL":
        key_risks.append("target_gap_signal_in_fail_band")

    payload = {
        "milestone_status": checkpoint.get("status"),
        "milestone_decision": checkpoint.get("milestone_decision"),
        "checkpoint_score": checkpoint.get("checkpoint_score"),
        "moat_public_score": scoreboard.get("moat_public_score"),
        "alignment_score": alignment.get("alignment_score"),
        "model_asset_momentum_status": checkpoint.get("model_asset_momentum_status"),
        "model_asset_momentum_score": checkpoint.get("model_asset_momentum_score"),
        "delta_total_real_models": checkpoint.get("delta_total_real_models"),
        "delta_large_models": checkpoint.get("delta_large_models"),
        "target_gap_pressure_index": target_gap_pressure,
        "model_asset_target_gap_score": target_gap_score,
        "target_gap_band": target_gap_band,
        "target_gap_supply_pressure_index": target_gap_supply_pressure,
        "target_gap_narrative_status": target_gap_narrative_status,
        "headline": f"GateForge milestone {checkpoint.get('milestone_decision')} at score {checkpoint.get('checkpoint_score')}",
        "key_risks": key_risks,
        "sources": {
            "milestone_checkpoint_summary": args.milestone_checkpoint_summary,
            "moat_public_scoreboard_summary": args.moat_public_scoreboard_summary,
            "snapshot_moat_alignment_summary": args.snapshot_moat_alignment_summary,
            "governance_decision_proofbook_summary": args.governance_decision_proofbook_summary,
            "failure_supply_plan_summary": args.failure_supply_plan_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out, payload)
    print(json.dumps({"milestone_status": payload.get("milestone_status"), "milestone_decision": payload.get("milestone_decision")}))
    if str(payload.get("milestone_status") or "") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
