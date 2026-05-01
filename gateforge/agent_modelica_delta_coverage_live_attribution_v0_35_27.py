from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_delta_portfolio_live_attribution_v0_35_26 import _case_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_delta_coverage_live_v0_35_27_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "delta_coverage_live_attribution_v0_35_27"


def build_delta_coverage_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_summary(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    portfolio_used_count = sum(1 for case in cases if case["portfolio_call_count"] > 0)
    multi_portfolio_count = sum(1 for case in cases if case["portfolio_call_count"] > 1)
    residual_matching_count = sum(1 for case in cases if case["portfolio_has_residual_matching_delta"])
    tested_candidate_count = sum(len(case["post_consistency_candidate_zero_flow_counts"]) for case in cases)
    if not rows:
        decision = "delta_coverage_live_run_missing"
    elif pass_count:
        decision = "delta_coverage_helped_sem22_pass"
    elif residual_matching_count and tested_candidate_count == 0:
        decision = "delta_coverage_reached_candidate_space_but_no_test"
    elif residual_matching_count:
        decision = "delta_coverage_covered_residual_delta_without_success"
    elif multi_portfolio_count:
        decision = "delta_coverage_revised_without_residual_match"
    elif portfolio_used_count:
        decision = "delta_coverage_used_without_residual_delta_coverage"
    else:
        decision = "delta_coverage_not_used"
    summary = {
        "version": "v0.35.27",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "delta_coverage_live_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "pass_count": pass_count,
        "portfolio_used_count": portfolio_used_count,
        "multi_portfolio_count": multi_portfolio_count,
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
