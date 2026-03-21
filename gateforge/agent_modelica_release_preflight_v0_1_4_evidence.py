from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_release_preflight_v0_1_4_evidence_v1"


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
    pass_pct = float(summary.get("all_scenarios_pass_pct") or 0.0)
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
    status = "PASS" if not reasons else "FAIL"
    details = {
        "success_count": success_count,
        "total_tasks": total_tasks,
        "all_scenarios_pass_pct": pass_pct,
        "llm_replan_used_count": replan_used_count,
        "llm_replan_switch_branch_success_count": switch_branch_success_count,
        "branch_selection_error_count": branch_selection_error_count,
    }
    return status, reasons, details


def _v5_branch_choice_status(summary: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    total_tasks = int(summary.get("total_tasks") or 0)
    pass_pct = float(summary.get("all_scenarios_pass_pct") or 0.0)
    branch_pct = float(summary.get("stage_2_branch_pct") or 0.0)
    llm_request_count_total = int(summary.get("llm_request_count_total") or 0)
    llm_replan_used_count = int(summary.get("llm_replan_used_count") or 0)
    branch_match_pct = max(
        float(summary.get("first_plan_branch_match_pct") or 0.0),
        float(summary.get("replan_branch_match_pct") or 0.0),
    )
    if not summary:
        reasons.append("v5_branch_choice_summary_missing")
    if total_tasks <= 0:
        reasons.append("v5_total_tasks_missing")
    if branch_pct <= 0.0:
        reasons.append("v5_branch_headroom_not_observed")
    if llm_request_count_total <= 0:
        reasons.append("v5_llm_usage_missing")
    if llm_replan_used_count <= 0:
        reasons.append("v5_llm_replan_missing")
    if branch_match_pct <= 0.0:
        reasons.append("v5_branch_match_signal_missing")
    status = "PASS" if not reasons else "FAIL"
    details = {
        "all_scenarios_pass_pct": pass_pct,
        "stage_2_branch_pct": branch_pct,
        "llm_request_count_total": llm_request_count_total,
        "llm_replan_used_count": llm_replan_used_count,
        "branch_match_pct": branch_match_pct,
    }
    return status, reasons, details


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment release preflight summary with v0.1.4 evidence checks")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--v4-replan-summary", required=True)
    parser.add_argument("--v5-branch-summary", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    out_path = str(args.out or args.summary)
    summary = _load_json(args.summary)
    v4_summary = _load_json(args.v4_replan_summary)
    v5_summary = _load_json(args.v5_branch_summary)

    v4_status, v4_reasons, v4_details = _v4_replan_status(v4_summary)
    v5_status, v5_reasons, v5_details = _v5_branch_choice_status(v5_summary)

    payload = dict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["v014_v4_llm_replan_status"] = v4_status
    payload["v014_v5_branch_choice_status"] = v5_status
    payload["v014_v4_llm_replan"] = {
        **v4_details,
        "reasons": v4_reasons,
        "summary_path": str(args.v4_replan_summary),
    }
    payload["v014_v5_branch_choice"] = {
        **v5_details,
        "reasons": v5_reasons,
        "summary_path": str(args.v5_branch_summary),
    }
    payload["v014_v5_stage_2_branch_pct"] = float(v5_details.get("stage_2_branch_pct") or 0.0)
    payload["v014_v5_llm_replan_used_count"] = int(v5_details.get("llm_replan_used_count") or 0)

    reasons = [str(x) for x in payload.get("reasons") or [] if isinstance(x, str)]
    if v4_status != "PASS":
        reasons.append("v014_v4_llm_replan_not_pass")
    if v5_status != "PASS":
        reasons.append("v014_v5_branch_choice_not_pass")
    payload["reasons"] = reasons

    status = str(payload.get("status") or "PASS").strip().upper() or "PASS"
    if not _status_ok(v4_status) or not _status_ok(v5_status):
        status = "FAIL"
    payload["status"] = status

    _write_json(out_path, payload)
    print(json.dumps(payload))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
