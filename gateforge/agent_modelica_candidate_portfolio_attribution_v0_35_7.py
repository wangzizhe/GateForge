from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_base_submit_checkpoint_attribution_v0_35_4 import (
    _checkpoint_guard_violations,
    _checkpoint_message_count,
)
from .agent_modelica_connector_flow_family_live_attribution_v0_35_1 import _classify_run
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "base_candidate_portfolio_checkpoint_live_v0_35_7"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_portfolio_attribution_v0_35_7"


def build_candidate_portfolio_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = _classify_run(row)
        case["checkpoint_message_count"] = _checkpoint_message_count(row)
        case["checkpoint_guard_violations"] = _checkpoint_guard_violations(row)
        cases.append(case)
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    checkpoint_message_count = sum(int(case["checkpoint_message_count"]) for case in cases)
    check_model_call_count = sum(int(case["check_model_call_count"]) for case in cases)
    if not rows:
        decision = "missing_candidate_portfolio_live_run"
    elif pass_count:
        decision = "candidate_portfolio_has_live_success"
    elif success_candidate_seen_count:
        decision = "candidate_portfolio_reaches_success_without_delivery"
    else:
        decision = "candidate_portfolio_prompt_does_not_improve_discovery"
    summary = {
        "version": "v0.35.7",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "candidate_portfolio_attribution",
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": pass_count,
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "success_candidate_seen_count": success_candidate_seen_count,
        "checkpoint_message_count": checkpoint_message_count,
        "check_model_call_count": check_model_call_count,
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
    out_dir.mkdir(parents=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
