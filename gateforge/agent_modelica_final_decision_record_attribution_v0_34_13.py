from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "final_decision_record_live_probe_v0_34_13_sem19_run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "final_decision_record_attribution_v0_34_13"


def _tool_names(step: dict[str, Any]) -> list[str]:
    return [
        str(call.get("name") or "")
        for call in step.get("tool_calls", [])
        if isinstance(call, dict)
    ]


def _result_text(step: dict[str, Any], tool_name: str) -> str:
    return "\n".join(
        str(result.get("result") or "")
        for result in step.get("tool_results", [])
        if isinstance(result, dict) and result.get("name") == tool_name
    )


def _success_seen(step: dict[str, Any]) -> bool:
    return (
        'resultFile = "/workspace/' in _result_text(step, "check_model")
        or 'resultFile = "/workspace/' in _result_text(step, "simulate_model")
    )


def build_final_decision_record_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    missing_run = not rows
    row = rows[0] if rows else {}
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    tool_sequence = [name for step in steps for name in _tool_names(step)]
    success_steps = [int(step.get("step") or 0) for step in steps if _success_seen(step)]
    oracle_call_count = tool_sequence.count("reusable_contract_oracle_diagnostic")
    record_call_count = tool_sequence.count("record_final_decision_rationale")
    if missing_run:
        decision = "missing_live_run"
    elif record_call_count:
        decision = "final_decision_record_used"
    elif success_steps and not oracle_call_count:
        decision = "success_candidate_seen_but_oracle_and_record_not_used"
    elif not success_steps:
        decision = "record_tool_trigger_not_reached"
    else:
        decision = "oracle_or_record_usage_incomplete"
    summary = {
        "version": "v0.34.13",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "final_decision_record_live_attribution",
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "success_evidence_steps": success_steps,
        "oracle_call_count": oracle_call_count,
        "record_call_count": record_call_count,
        "submit_call_count": tool_sequence.count("submit_final"),
        "tool_sequence": tool_sequence,
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
