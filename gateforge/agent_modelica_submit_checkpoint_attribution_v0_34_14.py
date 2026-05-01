from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "reusable_contract_submit_checkpoint_live_probe_v0_34_14_sem19_run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "reusable_contract_submit_checkpoint_attribution_v0_34_14"


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
    return 'resultFile = "/workspace/' in _result_text(step, "check_model") or 'resultFile = "/workspace/' in _result_text(
        step,
        "simulate_model",
    )


def _balanced_seen(step: dict[str, Any]) -> bool:
    text = _result_text(step, "check_model") + _result_text(step, "simulate_model")
    return "has 24 equation(s) and 24 variable(s)" in text


def build_submit_checkpoint_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    row = rows[0] if rows else {}
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    tool_sequence = [name for step in steps for name in _tool_names(step)]
    success_steps = [int(step.get("step") or 0) for step in steps if _success_seen(step)]
    balanced_steps = [int(step.get("step") or 0) for step in steps if _balanced_seen(step)]
    checkpoint_message_count = sum(len(step.get("checkpoint_messages", [])) for step in steps)
    checkpoint_guard_count = sum(len(step.get("checkpoint_guard_violations", [])) for step in steps)
    if not rows:
        decision = "missing_live_run"
    elif success_steps:
        decision = "submit_checkpoint_reached_success_evidence"
    elif balanced_steps:
        decision = "balanced_candidate_seen_without_simulation_success"
    else:
        decision = "submit_checkpoint_trigger_not_reached"
    summary = {
        "version": "v0.34.14",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "reusable_contract_submit_checkpoint_attribution",
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "success_evidence_steps": success_steps,
        "balanced_candidate_steps": balanced_steps,
        "checkpoint_message_count": checkpoint_message_count,
        "checkpoint_guard_count": checkpoint_guard_count,
        "oracle_call_count": tool_sequence.count("reusable_contract_oracle_diagnostic"),
        "record_call_count": tool_sequence.count("record_final_decision_rationale"),
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
