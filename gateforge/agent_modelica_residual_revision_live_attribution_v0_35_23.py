from __future__ import annotations

import json
from pathlib import Path

from .agent_modelica_residual_obedience_attribution_v0_35_22 import (
    TARGET_CASE_ID,
    _case_row,
    write_outputs,
)
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_residual_revision_live_v0_35_23_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "residual_revision_live_attribution_v0_35_23"


def build_residual_revision_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_row(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    violation_count = sum(1 for case in cases if case["post_consistency_over_residual_candidate_count"] > 0)
    if not rows:
        decision = "residual_revision_live_run_missing"
    elif pass_count and violation_count:
        decision = "residual_revision_helped_sem22_pass_after_initial_violation"
    elif pass_count:
        decision = "residual_revision_helped_sem22_pass"
    elif violation_count:
        decision = "residual_revision_guidance_not_obeyed"
    else:
        decision = "residual_revision_obeyed_without_success"
    summary = {
        "version": "v0.35.23",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "residual_revision_live_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "pass_count": pass_count,
        "post_consistency_violation_count": violation_count,
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
