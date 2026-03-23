from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_release_preflight_v0_1_5_evidence_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _status_ok(value: str) -> bool:
    return str(value or "").strip().upper() == "PASS"


def _v4_replan_status(summary: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    success_count = int(summary.get("success_count") or 0)
    total_tasks = int(summary.get("total_tasks") or 0)
    replan_used_count = int(summary.get("llm_replan_used_count") or 0)
    switch_branch_success_count = int(summary.get("llm_replan_switch_branch_success_count") or 0)
    branch_selection_error_count = int(summary.get("branch_selection_error_count") or 0)
    if not summary:
        reasons.append("v4_replan_summary_missing")
    if total_tasks <= 0 or success_count < total_tasks:
        reasons.append("v4_replan_not_saturated")
    if replan_used_count <= 0:
        reasons.append("v4_replan_signal_missing")
    if switch_branch_success_count <= 0:
        reasons.append("v4_switch_branch_success_missing")
    if branch_selection_error_count != 0:
        reasons.append("v4_branch_selection_error_present")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {
            "success_count": success_count,
            "total_tasks": total_tasks,
            "all_scenarios_pass_pct": float(summary.get("all_scenarios_pass_pct") or 0.0),
            "llm_replan_used_count": replan_used_count,
            "llm_replan_switch_branch_success_count": switch_branch_success_count,
            "branch_selection_error_count": branch_selection_error_count,
        },
    )


def _v5_branch_choice_status(gemini_summary: dict, rule_summary: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    total_tasks = int(gemini_summary.get("total_tasks") or 0)
    gemini_success_count = int(gemini_summary.get("success_count") or 0)
    rule_success_count = int(rule_summary.get("success_count") or 0)
    branch_error_count = int(gemini_summary.get("branch_selection_error_count") or 0)
    replan_used_count = int(gemini_summary.get("llm_replan_used_count") or 0)
    branch_match_pct = max(
        float(gemini_summary.get("first_plan_branch_match_pct") or 0.0),
        float(gemini_summary.get("replan_branch_match_pct") or 0.0),
    )
    if not gemini_summary:
        reasons.append("v5_gemini_summary_missing")
    if not rule_summary:
        reasons.append("v5_rule_summary_missing")
    if total_tasks <= 0:
        reasons.append("v5_total_tasks_missing")
    if gemini_success_count < max(5, total_tasks - 1):
        reasons.append("v5_gemini_success_below_release_floor")
    if gemini_success_count <= rule_success_count:
        reasons.append("v5_gemini_uplift_missing")
    if branch_error_count > 1:
        reasons.append("v5_branch_selection_errors_too_high")
    if replan_used_count <= 0:
        reasons.append("v5_llm_replan_missing")
    if branch_match_pct <= 0.0:
        reasons.append("v5_branch_match_signal_missing")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {
            "gemini_success_count": gemini_success_count,
            "rule_success_count": rule_success_count,
            "success_delta": gemini_success_count - rule_success_count,
            "total_tasks": total_tasks,
            "all_scenarios_pass_pct": float(gemini_summary.get("all_scenarios_pass_pct") or 0.0),
            "stage_2_branch_pct": float(gemini_summary.get("stage_2_branch_pct") or 0.0),
            "branch_selection_error_count": branch_error_count,
            "llm_replan_used_count": replan_used_count,
            "branch_match_pct": branch_match_pct,
        },
    )


def _v5_guided_search_status(summary: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    guided_used_count = int(summary.get("llm_guided_search_used_count") or 0)
    budget_followed_count = int(summary.get("search_budget_followed_count") or 0)
    budget_helped_count = int(summary.get("llm_budget_helped_resolution_count") or 0)
    guided_resolution_count = int(summary.get("llm_guided_search_resolution_count") or 0)
    if not summary:
        reasons.append("v5_guided_search_summary_missing")
    if guided_used_count <= 0:
        reasons.append("v5_guided_search_not_used")
    if budget_followed_count <= 0:
        reasons.append("v5_guided_search_budget_not_followed")
    if budget_helped_count <= 0 and guided_resolution_count <= 0:
        reasons.append("v5_guided_search_resolution_signal_missing")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {
            "llm_guided_search_used_count": guided_used_count,
            "search_budget_followed_count": budget_followed_count,
            "llm_budget_helped_resolution_count": budget_helped_count,
            "llm_guided_search_resolution_count": guided_resolution_count,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment release preflight summary with v0.1.5 evidence checks")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--v4-replan-summary", required=True)
    parser.add_argument("--v5-gemini-summary", required=True)
    parser.add_argument("--v5-rule-summary", required=True)
    parser.add_argument("--decision-quality-gate", default=None,
                        help="Optional path to decision_quality_gate.json")
    parser.add_argument("--out")
    args = parser.parse_args()

    out_path = str(args.out or args.summary)
    summary = _load_json(args.summary)
    v4_summary = _load_json(args.v4_replan_summary)
    v5_gemini_summary = _load_json(args.v5_gemini_summary)
    v5_rule_summary = _load_json(args.v5_rule_summary)
    dq_gate = _load_json(args.decision_quality_gate) if args.decision_quality_gate else {}

    v4_status, v4_reasons, v4_details = _v4_replan_status(v4_summary)
    v5_branch_status, v5_branch_reasons, v5_branch_details = _v5_branch_choice_status(v5_gemini_summary, v5_rule_summary)
    v5_guided_status, v5_guided_reasons, v5_guided_details = _v5_guided_search_status(v5_gemini_summary)

    payload = dict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["v015_v4_llm_replan_status"] = v4_status
    payload["v015_v5_branch_choice_status"] = v5_branch_status
    payload["v015_v5_guided_search_status"] = v5_guided_status
    payload["v015_v4_llm_replan"] = {**v4_details, "reasons": v4_reasons, "summary_path": str(args.v4_replan_summary)}
    payload["v015_v5_branch_choice"] = {
        **v5_branch_details,
        "reasons": v5_branch_reasons,
        "gemini_summary_path": str(args.v5_gemini_summary),
        "rule_summary_path": str(args.v5_rule_summary),
    }
    payload["v015_v5_guided_search"] = {
        **v5_guided_details,
        "reasons": v5_guided_reasons,
        "summary_path": str(args.v5_gemini_summary),
    }
    payload["v015_v5_success_delta"] = int(v5_branch_details.get("success_delta") or 0)
    payload["v015_v5_branch_selection_error_count"] = int(v5_branch_details.get("branch_selection_error_count") or 0)
    payload["v015_v5_llm_guided_search_used_count"] = int(v5_guided_details.get("llm_guided_search_used_count") or 0)

    # Decision quality gate (optional, non-blocking: NEEDS_REVIEW surfaces in reasons only)
    dq_status = str(dq_gate.get("status") or "").strip().upper() if dq_gate else ""
    payload["v015_decision_quality_gate_status"] = dq_status or "missing"
    if dq_status and dq_status != "PASS":
        payload["v015_decision_quality_gate"] = {
            "status": dq_status,
            "primary_reason": str(dq_gate.get("primary_reason") or ""),
            "checks": dq_gate.get("checks") or {},
        }

    reasons = [str(x) for x in payload.get("reasons") or [] if isinstance(x, str)]
    if v4_status != "PASS":
        reasons.append("v015_v4_llm_replan_not_pass")
    if v5_branch_status != "PASS":
        reasons.append("v015_v5_branch_choice_not_pass")
    if v5_guided_status != "PASS":
        reasons.append("v015_v5_guided_search_not_pass")
    if dq_status == "NEEDS_REVIEW":
        reasons.append("v015_decision_quality_needs_review")
    elif dq_status == "FAIL":
        reasons.append("v015_decision_quality_fail")
    payload["reasons"] = reasons

    status = str(payload.get("status") or "PASS").strip().upper() or "PASS"
    if not _status_ok(v4_status) or not _status_ok(v5_branch_status) or not _status_ok(v5_guided_status):
        status = "FAIL"
    # Decision quality FAIL also fails the release; NEEDS_REVIEW only surfaces in reasons
    if dq_status == "FAIL":
        status = "FAIL"
    payload["status"] = status

    _write_json(out_path, payload)
    print(json.dumps(payload))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
