from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_semantics_attribution_v0_34_15 import (
    _balanced_without_success,
    _has_success,
    _tool_names,
)
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_submit_checkpoint_live_probe_v0_34_16_sem19_run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_submit_checkpoint_attribution_v0_34_16"


def build_connector_flow_submit_checkpoint_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    row = rows[0] if rows else {}
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    tool_sequence = [name for step in steps for name in _tool_names(step)]
    success_steps = [int(step.get("step") or 0) for step in steps if _has_success(step)]
    balanced_without_success_steps = [int(step.get("step") or 0) for step in steps if _balanced_without_success(step)]
    checkpoint_message_count = sum(len(step.get("checkpoint_messages", [])) for step in steps)
    checkpoint_guard_count = sum(len(step.get("checkpoint_guard_violations", [])) for step in steps)
    if not rows:
        decision = "missing_live_run"
    elif success_steps:
        decision = "submit_checkpoint_reached_success_evidence"
    elif tool_sequence.count("connector_flow_semantics_diagnostic") > 0:
        decision = "flow_diagnostic_invoked_but_submit_checkpoint_not_reached"
    else:
        decision = "submit_checkpoint_not_reached"
    summary = {
        "version": "v0.34.16",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "connector_flow_submit_checkpoint_attribution",
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "success_evidence_steps": success_steps,
        "balanced_without_success_steps": balanced_without_success_steps,
        "checkpoint_message_count": checkpoint_message_count,
        "checkpoint_guard_count": checkpoint_guard_count,
        "diagnostic_call_count": tool_sequence.count("connector_flow_semantics_diagnostic"),
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
