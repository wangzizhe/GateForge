from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_semantics_live_probe_v0_34_15_sem19_run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_semantics_attribution_v0_34_15"


def _tool_names(step: dict[str, Any]) -> list[str]:
    return [
        str(call.get("name") or "")
        for call in step.get("tool_calls", [])
        if isinstance(call, dict)
    ]


def _tool_result_text(step: dict[str, Any], tool_name: str) -> str:
    return "\n".join(
        str(result.get("result") or "")
        for result in step.get("tool_results", [])
        if isinstance(result, dict) and result.get("name") == tool_name
    )


def _candidate_texts(step: dict[str, Any]) -> list[str]:
    return [
        str(call.get("arguments", {}).get("model_text") or "")
        for call in step.get("tool_calls", [])
        if isinstance(call, dict) and str(call.get("arguments", {}).get("model_text") or "").strip()
    ]


def _has_success(step: dict[str, Any]) -> bool:
    return 'resultFile = "/workspace/' in _tool_result_text(step, "check_model") or 'resultFile = "/workspace/' in _tool_result_text(
        step,
        "simulate_model",
    )


def _balanced_without_success(step: dict[str, Any]) -> bool:
    text = _tool_result_text(step, "check_model") + _tool_result_text(step, "simulate_model")
    return "has 24 equation(s) and 24 variable(s)" in text and 'resultFile = "/workspace/' not in text


def _zero_current_candidate(text: str) -> bool:
    compact = "".join(str(text).split())
    return ".i=0;" in compact


def _aggregate_flow_candidate(text: str) -> bool:
    compact = "".join(str(text).split())
    return ".i+" in compact and ".i=0;" in compact


def build_connector_flow_semantics_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    row = rows[0] if rows else {}
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    tool_sequence = [name for step in steps for name in _tool_names(step)]
    candidate_texts = [text for step in steps for text in _candidate_texts(step)]
    diagnostic_call_count = tool_sequence.count("connector_flow_semantics_diagnostic")
    success_steps = [int(step.get("step") or 0) for step in steps if _has_success(step)]
    balanced_without_success_steps = [int(step.get("step") or 0) for step in steps if _balanced_without_success(step)]
    zero_current_candidate_count = sum(1 for text in candidate_texts if _zero_current_candidate(text))
    aggregate_flow_candidate_count = sum(1 for text in candidate_texts if _aggregate_flow_candidate(text))
    if not rows:
        decision = "missing_live_run"
    elif diagnostic_call_count and not success_steps:
        decision = "flow_semantics_diagnostic_invoked_without_candidate_discovery_gain"
    elif diagnostic_call_count and success_steps:
        decision = "flow_semantics_diagnostic_reached_success_candidate"
    else:
        decision = "flow_semantics_diagnostic_not_invoked"
    summary = {
        "version": "v0.34.15",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "connector_flow_semantics_live_attribution",
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "diagnostic_call_count": diagnostic_call_count,
        "success_evidence_steps": success_steps,
        "balanced_without_success_steps": balanced_without_success_steps,
        "zero_current_candidate_count": zero_current_candidate_count,
        "aggregate_flow_candidate_count": aggregate_flow_candidate_count,
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
