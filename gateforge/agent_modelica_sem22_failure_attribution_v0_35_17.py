from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_hypothesis_blind_scoring_v0_35_14 import _tool_calls

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_CASE_ID = "sem_22_arrayed_three_branch_probe_bus"
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_state_checkpoint_live_v0_35_10",
    REPO_ROOT / "artifacts" / "connector_flow_hypothesis_checkpoint_live_v0_35_13",
    REPO_ROOT / "artifacts" / "connector_flow_minimal_contract_live_v0_35_15",
    REPO_ROOT / "artifacts" / "connector_flow_minimal_contract_repeat_v0_35_16_run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "sem22_failure_attribution_v0_35_17"


def _json_result(result: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(result or ""))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_result_payloads(row: dict[str, Any], tool_name: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if not isinstance(result, dict) or result.get("name") != tool_name:
                continue
            payload = _json_result(result.get("result"))
            if payload:
                payloads.append(payload)
    return payloads


def _tool_call_count(row: dict[str, Any], tool_name: str) -> int:
    count = 0
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name") == tool_name:
                count += 1
    return count


def _success_evidence_steps(row: dict[str, Any]) -> list[int]:
    steps: list[int] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if 'resultFile = "/workspace/' in str(result.get("result") or ""):
                steps.append(int(step.get("step") or 0))
                break
    return steps


def _max_connection_member_count(payloads: list[dict[str, Any]]) -> int:
    max_count = 0
    for payload in payloads:
        for conn_set in payload.get("connection_sets", []):
            if isinstance(conn_set, dict):
                max_count = max(max_count, int(conn_set.get("member_count") or 0))
    return max_count


def _run_row(run_dir: Path, target_case_id: str) -> dict[str, Any] | None:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    if not rows:
        return None
    row = rows[0]
    state_payloads = _tool_result_payloads(row, "connector_flow_state_diagnostic")
    hypotheses = _tool_calls(row, "record_repair_hypothesis")
    return {
        "run_id": run_dir.name,
        "tool_profile": str(row.get("tool_profile") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "step_count": int(row.get("step_count") or len(row.get("steps", []))),
        "success_evidence_steps": _success_evidence_steps(row),
        "state_diagnostic_call_count": _tool_call_count(row, "connector_flow_state_diagnostic"),
        "hypothesis_count": len(hypotheses),
        "hypothesis_expected_deltas": [
            item.get("expected_equation_delta") for item in hypotheses if "expected_equation_delta" in item
        ],
        "max_connection_member_count": _max_connection_member_count(state_payloads),
    }


def build_sem22_failure_attribution(
    *,
    run_dirs: list[Path] | None = None,
    target_case_id: str = TARGET_CASE_ID,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    runs: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for run_dir in dirs:
        row = _run_row(run_dir, target_case_id)
        if row is None:
            missing_runs.append(run_dir.name)
        else:
            runs.append(row)
    pass_count = sum(1 for row in runs if row["final_verdict"] == "PASS")
    success_candidate_seen_count = sum(1 for row in runs if row["success_evidence_steps"])
    hypothesis_runs = sum(1 for row in runs if row["hypothesis_count"] > 0)
    large_bus_observed_runs = sum(1 for row in runs if row["max_connection_member_count"] >= 6)
    if missing_runs:
        decision = "sem22_attribution_incomplete"
    elif pass_count:
        decision = "sem22_has_successful_profile"
    elif success_candidate_seen_count:
        decision = "sem22_success_candidate_not_submitted"
    elif large_bus_observed_runs:
        decision = "sem22_failure_concentrates_on_arrayed_shared_bus_reasoning"
    elif hypothesis_runs:
        decision = "sem22_no_success_candidate_after_semantic_hypotheses"
    else:
        decision = "sem22_failure_mode_unclear"
    summary = {
        "version": "v0.35.17",
        "status": "PASS" if runs and not missing_runs else "REVIEW",
        "analysis_scope": "sem22_failure_attribution",
        "target_case_id": target_case_id,
        "run_count": len(runs),
        "missing_runs": missing_runs,
        "pass_count": pass_count,
        "success_candidate_seen_count": success_candidate_seen_count,
        "hypothesis_runs": hypothesis_runs,
        "large_bus_observed_runs": large_bus_observed_runs,
        "runs": runs,
        "decision": decision,
        "discipline": {
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
