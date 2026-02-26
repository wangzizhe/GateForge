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


def _to_list_of_str(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, str)]


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    integrity = payload.get("integrity", {}) if isinstance(payload.get("integrity"), dict) else {}
    lines = [
        "# GateForge Governance Evidence Pack",
        "",
        f"- status: `{payload.get('status')}`",
        f"- evidence_strength_score: `{payload.get('evidence_strength_score')}`",
        f"- evidence_sections_present: `{payload.get('evidence_sections_present')}`",
        f"- residual_risk_count: `{payload.get('residual_risk_count')}`",
        f"- integrity_status: `{integrity.get('status')}`",
        "",
        "## Proof Points",
        "",
    ]
    proof_points = _to_list_of_str(payload.get("proof_points"))
    if proof_points:
        for point in proof_points:
            lines.append(f"- `{point}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Residual Risks", ""])
    residual = _to_list_of_str(payload.get("residual_risks"))
    if residual:
        for risk in residual:
            lines.append(f"- `{risk}`")
    else:
        lines.append("- `none`")

    action_outcome = payload.get("action_outcome") if isinstance(payload.get("action_outcome"), dict) else {}
    lines.extend(["", "## Action Outcome", ""])
    lines.append(f"- backlog_open_tasks: `{action_outcome.get('backlog_open_tasks')}`")
    lines.append(f"- backlog_p0_count: `{action_outcome.get('backlog_p0_count')}`")
    lines.append(f"- replay_recommendation: `{action_outcome.get('replay_recommendation')}`")
    lines.append(f"- replay_status: `{action_outcome.get('replay_status')}`")
    lines.append(f"- replay_evaluation_score: `{action_outcome.get('replay_evaluation_score')}`")
    lines.append(f"- policy_patch_roi_score: `{action_outcome.get('policy_patch_roi_score')}`")

    lines.extend(["", "## Integrity Checks", ""])
    checks = integrity.get("checks") if isinstance(integrity.get("checks"), dict) else {}
    for key in sorted(checks.keys()):
        lines.append(f"- {key}: `{checks[key]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _integrity_checks(snapshot: dict, trend: dict) -> dict:
    checks = {
        "snapshot_present": "PASS" if isinstance(snapshot, dict) and bool(snapshot) else "FAIL",
        "snapshot_has_status": "PASS" if isinstance(snapshot.get("status"), str) else "FAIL",
        "snapshot_has_kpis": "PASS" if isinstance(snapshot.get("kpis"), dict) else "FAIL",
        "snapshot_has_risks": "PASS" if isinstance(snapshot.get("risks"), list) else "FAIL",
        "trend_present": "PASS" if isinstance(trend, dict) and bool(trend) else "FAIL",
        "trend_has_status_transition": "PASS"
        if isinstance((trend.get("trend") or {}).get("status_transition"), str)
        else "FAIL",
        "trend_has_severity": "PASS"
        if isinstance((trend.get("trend") or {}).get("severity_score"), int)
        and (trend.get("trend") or {}).get("severity_level") in {"low", "medium", "high"}
        else "FAIL",
    }
    fail_count = len([v for v in checks.values() if v != "PASS"])
    status = "PASS" if fail_count == 0 else "FAIL"
    return {"status": status, "checks": checks, "fail_count": fail_count}


def _source_present(payload: dict) -> bool:
    return isinstance(payload, dict) and bool(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build governance evidence pack from snapshot and companion artifacts")
    parser.add_argument("--snapshot-summary", required=True)
    parser.add_argument("--snapshot-trend", required=True)
    parser.add_argument("--failure-taxonomy-coverage", default=None)
    parser.add_argument("--failure-distribution-benchmark", default=None)
    parser.add_argument("--model-scale-ladder", default=None)
    parser.add_argument("--failure-policy-patch-advisor", default=None)
    parser.add_argument("--blind-spot-backlog", default=None)
    parser.add_argument("--policy-patch-replay-evaluator", default=None)
    parser.add_argument("--out", default="artifacts/dataset_governance_evidence_pack/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    snapshot = _load_json(args.snapshot_summary)
    trend = _load_json(args.snapshot_trend)
    taxonomy = _load_json(args.failure_taxonomy_coverage)
    distribution = _load_json(args.failure_distribution_benchmark)
    ladder = _load_json(args.model_scale_ladder)
    advisor = _load_json(args.failure_policy_patch_advisor)
    backlog = _load_json(args.blind_spot_backlog)
    replay_eval = _load_json(args.policy_patch_replay_evaluator)

    integrity = _integrity_checks(snapshot, trend)

    evidence_sources = {
        "snapshot": snapshot,
        "snapshot_trend": trend,
        "failure_taxonomy_coverage": taxonomy,
        "failure_distribution_benchmark": distribution,
        "model_scale_ladder": ladder,
        "failure_policy_patch_advisor": advisor,
        "blind_spot_backlog": backlog,
        "policy_patch_replay_evaluator": replay_eval,
    }
    evidence_sections_present = len([k for k, v in evidence_sources.items() if _source_present(v)])

    proof_points: list[str] = []
    if isinstance(snapshot.get("status"), str):
        proof_points.append(f"snapshot_status:{snapshot.get('status')}")
    if isinstance(((trend.get("trend") or {}).get("status_transition")), str):
        proof_points.append(f"snapshot_trend_transition:{(trend.get('trend') or {}).get('status_transition')}")
    if isinstance(taxonomy.get("status"), str):
        proof_points.append(f"taxonomy_status:{taxonomy.get('status')}")
    if isinstance(distribution.get("status"), str):
        proof_points.append(f"distribution_status:{distribution.get('status')}")
    if isinstance(ladder.get("status"), str):
        proof_points.append(f"model_scale_status:{ladder.get('status')}")
    if isinstance((advisor.get("advice") or {}).get("suggested_action"), str):
        proof_points.append(f"policy_patch_action:{(advisor.get('advice') or {}).get('suggested_action')}")
    if isinstance(backlog.get("status"), str):
        proof_points.append(f"backlog_status:{backlog.get('status')}")
    if isinstance(replay_eval.get("recommendation"), str):
        proof_points.append(f"replay_recommendation:{replay_eval.get('recommendation')}")

    residual_risks = _to_list_of_str(snapshot.get("risks"))
    residual_risks.extend(_to_list_of_str((trend.get("trend") or {}).get("new_risks")))
    residual_risks.extend(_to_list_of_str((taxonomy.get("alerts"))))
    residual_risks.extend(_to_list_of_str((distribution.get("alerts"))))
    residual_risks.extend(_to_list_of_str((ladder.get("alerts"))))
    residual_risks.extend(_to_list_of_str((replay_eval.get("reasons"))))
    residual_risks = sorted(set(residual_risks))

    replay_delta = replay_eval.get("delta") if isinstance(replay_eval.get("delta"), dict) else {}
    replay_score = int(replay_eval.get("evaluation_score", 0) or 0)
    policy_patch_roi_score = 50 + replay_score * 8
    policy_patch_roi_score += int(round(float(replay_delta.get("detection_rate", 0.0) or 0.0) * 100))
    policy_patch_roi_score -= int(round(float(replay_delta.get("false_positive_rate", 0.0) or 0.0) * 100))
    policy_patch_roi_score -= int(round(float(replay_delta.get("regression_rate", 0.0) or 0.0) * 100))
    policy_patch_roi_score = max(0, min(100, policy_patch_roi_score))

    action_outcome = {
        "backlog_open_tasks": int(backlog.get("total_open_tasks", 0) or 0),
        "backlog_p0_count": int(((backlog.get("priority_counts") or {}).get("P0", 0) or 0)),
        "replay_recommendation": replay_eval.get("recommendation"),
        "replay_status": replay_eval.get("status"),
        "replay_evaluation_score": replay_score,
        "policy_patch_roi_score": policy_patch_roi_score,
    }

    evidence_strength_score = 30
    evidence_strength_score += min(40, evidence_sections_present * 8)
    if integrity.get("status") == "PASS":
        evidence_strength_score += 15
    if str(snapshot.get("status") or "") == "PASS":
        evidence_strength_score += 10
    if str((trend.get("trend") or {}).get("severity_level") or "") in {"low", "medium", "high"}:
        evidence_strength_score += 5
    if str(replay_eval.get("status") or "") == "PASS":
        evidence_strength_score += 8
    if str(backlog.get("status") or "") == "NEEDS_REVIEW" and int(backlog.get("total_open_tasks", 0) or 0) > 0:
        evidence_strength_score -= 4
    evidence_strength_score += int((policy_patch_roi_score - 50) / 10)
    evidence_strength_score -= min(20, len(residual_risks) * 2)
    evidence_strength_score = max(0, min(100, evidence_strength_score))

    if integrity.get("status") != "PASS":
        status = "FAIL"
    elif evidence_strength_score < 60 or residual_risks:
        status = "NEEDS_REVIEW"
    else:
        status = "PASS"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence_strength_score": evidence_strength_score,
        "evidence_sections_present": evidence_sections_present,
        "residual_risk_count": len(residual_risks),
        "residual_risks": residual_risks,
        "proof_points": proof_points,
        "action_outcome": action_outcome,
        "integrity": integrity,
        "sources": {
            "snapshot_summary": args.snapshot_summary,
            "snapshot_trend": args.snapshot_trend,
            "failure_taxonomy_coverage": args.failure_taxonomy_coverage,
            "failure_distribution_benchmark": args.failure_distribution_benchmark,
            "model_scale_ladder": args.model_scale_ladder,
            "failure_policy_patch_advisor": args.failure_policy_patch_advisor,
            "blind_spot_backlog": args.blind_spot_backlog,
            "policy_patch_replay_evaluator": args.policy_patch_replay_evaluator,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "evidence_strength_score": evidence_strength_score}))
    if payload.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
