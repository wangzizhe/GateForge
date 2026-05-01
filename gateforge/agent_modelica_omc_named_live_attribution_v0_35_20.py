from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_arrayed_bus_live_attribution_v0_35_19 import _tool_call_count
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID, _success_evidence_steps

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_omc_named_live_v0_35_20_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "omc_named_live_attribution_v0_35_20"


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": str(row.get("case_id") or ""),
        "tool_profile": str(row.get("tool_profile") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "step_count": int(row.get("step_count") or len(row.get("steps", []))),
        "success_evidence_steps": _success_evidence_steps(row),
        "state_diagnostic_call_count": _tool_call_count(row, "connector_flow_state_diagnostic"),
        "arrayed_shared_bus_call_count": _tool_call_count(row, "arrayed_shared_bus_diagnostic"),
        "omc_unmatched_flow_call_count": _tool_call_count(row, "omc_unmatched_flow_diagnostic"),
        "hypothesis_call_count": _tool_call_count(row, "record_repair_hypothesis"),
    }


def build_omc_named_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_row(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    omc_named_tool_used_count = sum(1 for case in cases if case["omc_unmatched_flow_call_count"] > 0)
    if not rows:
        decision = "omc_named_live_run_missing"
    elif pass_count:
        decision = "omc_named_residual_diagnostic_helped_sem22_pass"
    elif success_candidate_seen_count:
        decision = "omc_named_profile_found_success_candidate_without_submit"
    elif omc_named_tool_used_count:
        decision = "omc_named_residual_diagnostic_discoverable_but_no_sem22_pass"
    else:
        decision = "omc_named_residual_diagnostic_not_used"
    summary = {
        "version": "v0.35.20",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "omc_named_live_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "pass_count": pass_count,
        "success_candidate_seen_count": success_candidate_seen_count,
        "omc_named_tool_used_count": omc_named_tool_used_count,
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
