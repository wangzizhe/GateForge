from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_delta_portfolio_live_attribution_v0_35_26 import _case_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_candidate_preference_live_v0_35_29_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_preference_live_attribution_v0_35_29"


def _preference_payloads(row: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if not isinstance(result, dict) or result.get("name") != "record_candidate_preference_rationale":
                continue
            try:
                payload = json.loads(str(result.get("result") or ""))
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _case_preference_summary(row: dict[str, Any]) -> dict[str, Any]:
    case = _case_summary(row)
    preferences = _preference_payloads(row)
    case.update(
        {
            "preference_call_count": len(preferences),
            "compiler_evidence_preferred_count": sum(
                1 for payload in preferences if payload.get("compiler_evidence_preferred")
            ),
            "preference_selected_deltas": [
                payload.get("selected_expected_equation_delta") for payload in preferences
            ],
            "preference_rejected_deltas": [
                payload.get("rejected_expected_equation_delta") for payload in preferences
            ],
        }
    )
    return case


def build_candidate_preference_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_preference_summary(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    preference_used_count = sum(1 for case in cases if case["preference_call_count"] > 0)
    compiler_evidence_preferred_count = sum(1 for case in cases if case["compiler_evidence_preferred_count"] > 0)
    tested_candidate_count = sum(len(case["post_consistency_candidate_zero_flow_counts"]) for case in cases)
    if not rows:
        decision = "candidate_preference_live_run_missing"
    elif pass_count:
        decision = "candidate_preference_helped_sem22_pass"
    elif compiler_evidence_preferred_count and tested_candidate_count:
        decision = "compiler_preference_recorded_but_test_failed"
    elif compiler_evidence_preferred_count:
        decision = "compiler_preference_recorded_without_test"
    elif preference_used_count:
        decision = "candidate_preference_used_without_compiler_priority"
    else:
        decision = "candidate_preference_not_used"
    summary = {
        "version": "v0.35.29",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "candidate_preference_live_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "pass_count": pass_count,
        "preference_used_count": preference_used_count,
        "compiler_evidence_preferred_count": compiler_evidence_preferred_count,
        "tested_candidate_count": tested_candidate_count,
        "cases": cases,
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
