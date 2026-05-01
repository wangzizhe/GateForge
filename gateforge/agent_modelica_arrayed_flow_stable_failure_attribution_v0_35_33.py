from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_preference_live_attribution_v0_35_29 import _case_preference_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_sem22_failure_attribution_v0_35_17 import _success_evidence_steps

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_base_checkpoint_live_v0_35_32"
DEFAULT_CANDIDATE_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_candidate_preference_live_v0_35_31"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_stable_failure_attribution_v0_35_33"


def _rows_by_case(run_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("case_id") or ""): row
        for row in load_jsonl(run_dir / "results.jsonl")
        if row.get("case_id")
    }


def _tool_names(row: dict[str, Any]) -> list[str]:
    return [
        str(call.get("name") or "")
        for step in row.get("steps", [])
        if isinstance(step, dict)
        for call in step.get("tool_calls", [])
        if isinstance(call, dict) and call.get("name")
    ]


def _failure_shape(case: dict[str, Any]) -> str:
    if case["success_evidence_steps"]:
        return "success_candidate_seen_but_not_final"
    if case["portfolio_call_count"] and not case["post_consistency_candidate_zero_flow_counts"]:
        return "candidate_space_recorded_without_execution"
    if case["post_consistency_candidate_zero_flow_counts"]:
        return "candidate_executed_without_success"
    return "no_candidate_execution"


def build_arrayed_flow_stable_failure_attribution(
    *,
    base_dir: Path = DEFAULT_BASE_DIR,
    candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    base_rows = _rows_by_case(base_dir)
    candidate_rows = _rows_by_case(candidate_dir)
    stable_failed_ids = sorted(
        case_id
        for case_id in set(base_rows) & set(candidate_rows)
        if base_rows[case_id].get("final_verdict") != "PASS"
        and candidate_rows[case_id].get("final_verdict") != "PASS"
    )
    cases: list[dict[str, Any]] = []
    for case_id in stable_failed_ids:
        candidate_case = _case_preference_summary(candidate_rows[case_id])
        cases.append(
            {
                "case_id": case_id,
                "base_tool_calls": _tool_names(base_rows[case_id]),
                "candidate_preference_tool_calls": _tool_names(candidate_rows[case_id]),
                "base_success_evidence_steps": _success_evidence_steps(base_rows[case_id]),
                "candidate_success_evidence_steps": candidate_case["success_evidence_steps"],
                "portfolio_expected_equation_deltas": candidate_case["portfolio_expected_equation_deltas"],
                "portfolio_has_residual_matching_delta": candidate_case["portfolio_has_residual_matching_delta"],
                "preference_call_count": candidate_case["preference_call_count"],
                "post_consistency_candidate_zero_flow_counts": candidate_case[
                    "post_consistency_candidate_zero_flow_counts"
                ],
                "failure_shape": _failure_shape(candidate_case),
            }
        )
    shape_counts: dict[str, int] = {}
    for case in cases:
        shape = str(case["failure_shape"])
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
    if not base_rows or not candidate_rows:
        decision = "stable_failure_attribution_incomplete"
    elif not cases:
        decision = "no_stable_failures_in_arrayed_flow_slice"
    elif len(shape_counts) > 1:
        decision = "stable_failures_are_family_level_but_heterogeneous"
    else:
        decision = "stable_failures_share_single_shape"
    summary = {
        "version": "v0.35.33",
        "status": "PASS" if base_rows and candidate_rows else "REVIEW",
        "analysis_scope": "arrayed_flow_stable_failure_attribution",
        "stable_failed_case_ids": stable_failed_ids,
        "stable_failed_count": len(cases),
        "failure_shape_counts": dict(sorted(shape_counts.items())),
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
