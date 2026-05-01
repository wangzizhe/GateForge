from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_preference_live_attribution_v0_35_29 import _case_preference_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_candidate_preference_live_v0_35_31"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_preference_family_attribution_v0_35_31"


def build_arrayed_flow_preference_family_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases = [_case_preference_summary(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    preference_used_count = sum(1 for case in cases if case["preference_call_count"] > 0)
    compiler_evidence_preferred_count = sum(1 for case in cases if case["compiler_evidence_preferred_count"] > 0)
    residual_matching_count = sum(1 for case in cases if case["portfolio_has_residual_matching_delta"])
    tested_candidate_count = sum(len(case["post_consistency_candidate_zero_flow_counts"]) for case in cases)
    failed_case_ids = [case["case_id"] for case in cases if case["final_verdict"] != "PASS"]
    passed_case_ids = [case["case_id"] for case in cases if case["final_verdict"] == "PASS"]
    if not rows:
        decision = "arrayed_flow_preference_family_run_missing"
    elif pass_count == len(cases):
        decision = "arrayed_flow_preference_profile_solves_family"
    elif residual_matching_count and preference_used_count:
        decision = "arrayed_flow_preference_failure_is_family_level_not_sem22_only"
    elif residual_matching_count:
        decision = "arrayed_flow_residual_matching_seen_without_preference_resolution"
    else:
        decision = "arrayed_flow_failure_mode_unclear"
    summary = {
        "version": "v0.35.31",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "arrayed_flow_preference_family_attribution",
        "case_count": len(cases),
        "pass_count": pass_count,
        "failed_case_ids": failed_case_ids,
        "passed_case_ids": passed_case_ids,
        "preference_used_count": preference_used_count,
        "compiler_evidence_preferred_count": compiler_evidence_preferred_count,
        "residual_matching_count": residual_matching_count,
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
