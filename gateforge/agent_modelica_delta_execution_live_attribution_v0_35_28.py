from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_delta_portfolio_live_attribution_v0_35_26 import _case_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_delta_execution_live_v0_35_28_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "delta_execution_live_attribution_v0_35_28"


def build_delta_execution_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_summary(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    residual_matching_count = sum(1 for case in cases if case["portfolio_has_residual_matching_delta"])
    tested_candidate_count = sum(len(case["post_consistency_candidate_zero_flow_counts"]) for case in cases)
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    if not rows:
        decision = "delta_execution_live_run_missing"
    elif pass_count:
        decision = "delta_execution_helped_sem22_pass"
    elif success_candidate_seen_count:
        decision = "delta_execution_found_success_candidate_without_submit"
    elif residual_matching_count and tested_candidate_count:
        decision = "delta_execution_tested_after_residual_match_without_success"
    elif residual_matching_count:
        decision = "delta_execution_reached_candidate_space_without_test"
    else:
        decision = "delta_execution_no_residual_delta_coverage"
    summary = {
        "version": "v0.35.28",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "delta_execution_live_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "pass_count": pass_count,
        "residual_matching_count": residual_matching_count,
        "tested_candidate_count": tested_candidate_count,
        "success_candidate_seen_count": success_candidate_seen_count,
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
