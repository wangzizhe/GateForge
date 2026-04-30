from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_semantics_attribution_v0_34_15 import (
    _balanced_without_success,
    _has_success,
    _tool_names,
)
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_family_live_v0_35_1"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_family_live_attribution_v0_35_1"


def _classify_run(row: dict[str, Any]) -> dict[str, Any]:
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    tool_sequence = [name for step in steps for name in _tool_names(step)]
    success_steps = [int(step.get("step") or 0) for step in steps if _has_success(step)]
    balanced_without_success_steps = [
        int(step.get("step") or 0)
        for step in steps
        if _balanced_without_success(step)
    ]
    submitted = bool(row.get("submitted"))
    if submitted and row.get("final_verdict") == "PASS":
        outcome_class = "submitted_success"
    elif success_steps:
        outcome_class = "success_candidate_seen_without_submit"
    elif balanced_without_success_steps:
        outcome_class = "balanced_without_simulation_success"
    else:
        outcome_class = "candidate_discovery_failure"
    return {
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": submitted,
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "diagnostic_call_count": tool_sequence.count("connector_flow_semantics_diagnostic"),
        "check_model_call_count": tool_sequence.count("check_model"),
        "simulate_model_call_count": tool_sequence.count("simulate_model"),
        "submit_call_count": tool_sequence.count("submit_final"),
        "success_evidence_steps": success_steps,
        "balanced_without_success_steps": balanced_without_success_steps,
        "outcome_class": outcome_class,
    }


def build_connector_flow_family_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases = [_classify_run(row) for row in rows]
    class_counts: dict[str, int] = {}
    for case in cases:
        outcome_class = str(case["outcome_class"])
        class_counts[outcome_class] = class_counts.get(outcome_class, 0) + 1
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    diagnostic_invoked_count = sum(1 for case in cases if case["diagnostic_call_count"] > 0)
    if not rows:
        decision = "missing_connector_flow_family_live_run"
    elif pass_count:
        decision = "connector_flow_family_has_live_successes"
    elif success_candidate_seen_count:
        decision = "connector_flow_family_exposes_submit_discipline_gap"
    elif diagnostic_invoked_count:
        decision = "connector_flow_family_exposes_candidate_discovery_gap"
    else:
        decision = "connector_flow_family_diagnostic_not_invoked"
    summary = {
        "version": "v0.35.1",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "connector_flow_family_live_attribution",
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": pass_count,
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "diagnostic_invoked_count": diagnostic_invoked_count,
        "success_candidate_seen_count": success_candidate_seen_count,
        "balanced_without_success_count": sum(1 for case in cases if case["balanced_without_success_steps"]),
        "outcome_class_counts": dict(sorted(class_counts.items())),
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
