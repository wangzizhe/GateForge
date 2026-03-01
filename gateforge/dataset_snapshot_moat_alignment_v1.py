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


def _status(payload: dict) -> str:
    return str(payload.get("status") or "UNKNOWN")


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Snapshot Moat Alignment v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- alignment_score: `{payload.get('alignment_score')}`",
        f"- contradiction_count: `{payload.get('contradiction_count')}`",
        f"- target_gap_pressure_index: `{(payload.get('signals') or {}).get('target_gap_pressure_index')}`",
        f"- model_asset_target_gap_score: `{(payload.get('signals') or {}).get('model_asset_target_gap_score')}`",
        f"- target_gap_supply_pressure_index: `{(payload.get('signals') or {}).get('target_gap_supply_pressure_index')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check consistency between governance snapshot and moat/public campaign signals")
    parser.add_argument("--governance-snapshot-summary", required=True)
    parser.add_argument("--governance-snapshot-trend-summary", required=True)
    parser.add_argument("--moat-public-scoreboard-summary", required=True)
    parser.add_argument("--mutation-campaign-tracker-summary", required=True)
    parser.add_argument("--modelica-library-provenance-guard-summary", default=None)
    parser.add_argument("--real-model-supply-health-summary", default=None)
    parser.add_argument("--modelica-release-candidate-gate-summary", default=None)
    parser.add_argument("--governance-decision-proofbook-summary", default=None)
    parser.add_argument("--failure-supply-plan-summary", default=None)
    parser.add_argument("--out", default="artifacts/dataset_snapshot_moat_alignment_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    snapshot = _load_json(args.governance_snapshot_summary)
    trend = _load_json(args.governance_snapshot_trend_summary)
    scoreboard = _load_json(args.moat_public_scoreboard_summary)
    campaign = _load_json(args.mutation_campaign_tracker_summary)
    provenance = _load_json(args.modelica_library_provenance_guard_summary)
    supply = _load_json(args.real_model_supply_health_summary)
    release_candidate = _load_json(args.modelica_release_candidate_gate_summary)
    proofbook = _load_json(args.governance_decision_proofbook_summary)
    failure_supply = _load_json(args.failure_supply_plan_summary)

    reasons: list[str] = []
    if not snapshot:
        reasons.append("governance_snapshot_summary_missing")
    if not trend:
        reasons.append("governance_snapshot_trend_summary_missing")
    if not scoreboard:
        reasons.append("moat_public_scoreboard_summary_missing")
    if not campaign:
        reasons.append("mutation_campaign_tracker_summary_missing")

    snapshot_status = _status(snapshot)
    trend_status = _status(trend)
    scoreboard_status = _status(scoreboard)
    campaign_status = _status(campaign)
    provenance_status = _status(provenance) if provenance else "NOT_PROVIDED"
    supply_status = _status(supply) if supply else "NOT_PROVIDED"
    release_candidate_status = _status(release_candidate) if release_candidate else "NOT_PROVIDED"
    proofbook_status = _status(proofbook) if proofbook else "NOT_PROVIDED"
    failure_supply_status = _status(failure_supply) if failure_supply else "NOT_PROVIDED"

    scoreboard_score = _to_float(scoreboard.get("moat_public_score", 0.0))
    campaign_completion = _to_float(campaign.get("completion_ratio_pct", 0.0))
    trend_severity = _to_int(((trend.get("trend") or {}).get("severity_score")) if isinstance(trend.get("trend"), dict) else 0)
    snapshot_risk_count = len(snapshot.get("risks") or []) if isinstance(snapshot.get("risks"), list) else 0
    unknown_license_ratio = _to_float(provenance.get("unknown_license_ratio_pct", 0.0)) if provenance else 0.0
    supply_health_score = _to_float(supply.get("supply_health_score", 0.0)) if supply else 0.0
    release_candidate_score = _to_float(release_candidate.get("release_candidate_score", 0.0)) if release_candidate else 0.0
    release_candidate_decision = str(release_candidate.get("candidate_decision") or "UNKNOWN") if release_candidate else "UNKNOWN"
    target_gap_pressure = _to_float(proofbook.get("target_gap_pressure_index", 0.0)) if proofbook else 0.0
    target_gap_score = _to_float(proofbook.get("model_asset_target_gap_score", 0.0)) if proofbook else 0.0
    target_gap_supply_pressure = _to_float(failure_supply.get("target_gap_supply_pressure_index", 0.0)) if failure_supply else 0.0

    contradictions: list[str] = []
    if snapshot_status == "PASS" and scoreboard_status in {"NEEDS_REVIEW", "FAIL"}:
        contradictions.append("snapshot_pass_but_scoreboard_not_pass")
    if snapshot_status == "PASS" and campaign_status in {"NEEDS_REVIEW", "FAIL"}:
        contradictions.append("snapshot_pass_but_campaign_not_pass")
    if scoreboard_score >= 85.0 and snapshot_status in {"NEEDS_REVIEW", "FAIL"}:
        contradictions.append("scoreboard_high_but_snapshot_not_pass")
    if campaign_completion < 70.0 and snapshot_status == "PASS":
        contradictions.append("campaign_completion_low_but_snapshot_pass")
    if trend_severity >= 6 and scoreboard_status == "PASS":
        contradictions.append("trend_severity_high_but_scoreboard_pass")
    if provenance and unknown_license_ratio > 20.0 and scoreboard_status == "PASS":
        contradictions.append("license_risk_high_but_scoreboard_pass")
    if snapshot_risk_count == 0 and scoreboard_status in {"NEEDS_REVIEW", "FAIL"}:
        contradictions.append("snapshot_no_risk_but_scoreboard_not_pass")
    if release_candidate_decision == "GO" and snapshot_status in {"NEEDS_REVIEW", "FAIL"}:
        contradictions.append("release_candidate_go_but_snapshot_not_pass")
    if release_candidate_decision == "HOLD" and scoreboard_score >= 85.0:
        contradictions.append("release_candidate_hold_but_public_score_high")
    if supply and supply_status == "NEEDS_REVIEW" and snapshot_status == "PASS":
        contradictions.append("supply_needs_review_but_snapshot_pass")
    if proofbook and target_gap_score >= 35.0 and snapshot_status == "PASS":
        contradictions.append("target_gap_high_but_snapshot_pass")
    if proofbook and target_gap_pressure < 60.0 and scoreboard_status == "PASS":
        contradictions.append("target_gap_pressure_low_but_scoreboard_pass")
    if failure_supply and target_gap_supply_pressure >= 65.0 and scoreboard_status == "PASS":
        contradictions.append("target_gap_supply_pressure_high_but_scoreboard_pass")

    alignment_score = round(
        max(
            0.0,
            min(
                100.0,
                100.0
                - (len(contradictions) * 12.0)
                - (8.0 if snapshot_status == "FAIL" else 0.0)
                - (6.0 if scoreboard_status == "FAIL" else 0.0)
                - (4.0 if campaign_status == "FAIL" else 0.0)
                - (2.0 if provenance_status == "FAIL" else 0.0),
            ),
        ),
        2,
    )

    followups: list[str] = []
    if contradictions:
        followups.append("reconcile_snapshot_and_scoreboard_gating")
    if campaign_completion < 80.0:
        followups.append("increase_weekly_mutation_campaign_throughput")
    if trend_severity >= 3:
        followups.append("address_snapshot_trend_alerts_before_public_release")
    if provenance and unknown_license_ratio > 10.0:
        followups.append("reduce_unknown_license_assets_in_modelica_library")
    if supply and supply_health_score < 75.0:
        followups.append("increase_real_model_supply_health_score")
    if release_candidate and release_candidate_score < 80.0:
        followups.append("raise_release_candidate_score_before_public_promotion")
    if proofbook and target_gap_score >= 30.0:
        followups.append("reduce_model_asset_target_gap_score")
    if proofbook and target_gap_pressure < 60.0:
        followups.append("increase_target_gap_pressure_index")
    if failure_supply and target_gap_supply_pressure >= 65.0:
        followups.append("lower_target_gap_supply_pressure_index")

    alerts: list[str] = []
    if contradictions:
        alerts.append("snapshot_moat_signal_contradictions_present")
    if alignment_score < 75.0:
        alerts.append("alignment_score_below_target")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "alignment_score": alignment_score,
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "followups": followups,
        "alerts": alerts,
        "signals": {
            "snapshot_status": snapshot_status,
            "trend_status": trend_status,
            "scoreboard_status": scoreboard_status,
            "campaign_status": campaign_status,
            "provenance_status": provenance_status,
            "supply_status": supply_status,
            "release_candidate_status": release_candidate_status,
            "proofbook_status": proofbook_status,
            "failure_supply_status": failure_supply_status,
            "scoreboard_score": scoreboard_score,
            "campaign_completion_ratio_pct": campaign_completion,
            "trend_severity_score": trend_severity,
            "snapshot_risk_count": snapshot_risk_count,
            "provenance_unknown_license_ratio_pct": unknown_license_ratio,
            "supply_health_score": supply_health_score,
            "release_candidate_score": release_candidate_score,
            "release_candidate_decision": release_candidate_decision,
            "target_gap_pressure_index": target_gap_pressure,
            "model_asset_target_gap_score": target_gap_score,
            "target_gap_supply_pressure_index": target_gap_supply_pressure,
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "governance_snapshot_summary": args.governance_snapshot_summary,
            "governance_snapshot_trend_summary": args.governance_snapshot_trend_summary,
            "moat_public_scoreboard_summary": args.moat_public_scoreboard_summary,
            "mutation_campaign_tracker_summary": args.mutation_campaign_tracker_summary,
            "modelica_library_provenance_guard_summary": args.modelica_library_provenance_guard_summary,
            "real_model_supply_health_summary": args.real_model_supply_health_summary,
            "modelica_release_candidate_gate_summary": args.modelica_release_candidate_gate_summary,
            "governance_decision_proofbook_summary": args.governance_decision_proofbook_summary,
            "failure_supply_plan_summary": args.failure_supply_plan_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "alignment_score": alignment_score, "contradiction_count": len(contradictions)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
