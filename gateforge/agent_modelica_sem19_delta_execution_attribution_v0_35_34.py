from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_delta_execution_live_attribution_v0_35_28 import (
    build_delta_execution_live_attribution,
)
from .agent_modelica_delta_portfolio_live_attribution_v0_35_26 import _case_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "sem19_delta_execution_live_v0_35_34"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "sem19_delta_execution_attribution_v0_35_34"
TARGET_CASE_ID = "sem_19_arrayed_shared_probe_bus"


def build_sem19_delta_execution_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_delta_execution_live_attribution(
        run_dir=run_dir,
        out_dir=out_dir,
        target_case_id=TARGET_CASE_ID,
    )
    summary["version"] = "v0.35.34"
    summary["analysis_scope"] = "sem19_delta_execution_attribution"
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == TARGET_CASE_ID]
    cases = [_case_summary(row) for row in rows]
    if not rows:
        decision = "sem19_delta_execution_run_missing"
    elif any(case["final_verdict"] == "PASS" for case in cases):
        decision = "sem19_delta_execution_helped_pass"
    elif any(case["portfolio_has_residual_matching_delta"] for case in cases) and any(
        case["post_consistency_candidate_zero_flow_counts"] for case in cases
    ):
        decision = "sem19_residual_matching_candidate_executed_without_success"
    elif any(case["portfolio_has_residual_matching_delta"] for case in cases):
        decision = "sem19_residual_matching_candidate_not_executed"
    else:
        decision = "sem19_no_residual_matching_candidate"
    summary["decision"] = decision
    return summary
