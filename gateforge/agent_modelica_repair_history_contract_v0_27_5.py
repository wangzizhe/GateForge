from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "repair_history_contract_v0_27_5"

FORBIDDEN_HISTORY_TERMS = (
    "root_cause_hint",
    "repair_hint",
    "expected_fix",
    "target_patch",
    "deterministic_diagnosis",
    "routing_decision",
)


def build_canonical_repair_history() -> list[dict[str, Any]]:
    return [
        {
            "round": 1,
            "provider": str(os.getenv("LLM_PROVIDER") or "deepseek").strip(),
            "patched_text_present": True,
            "model_changed": True,
            "check_pass": False,
            "check_pass_after_patch": False,
            "input_omc_summary": "Error: Wrong number of subscripts in R1Resistance[1].",
            "post_patch_omc_summary": "Error: Too few equations, under-determined system.",
            "omc_summary": "Error: Too few equations, under-determined system.",
        }
    ]


def validate_repair_history_prompt(prompt: str) -> list[str]:
    errors: list[str] = []
    if "OMC before this patch:" not in prompt:
        errors.append("missing_input_omc_transition")
    if "OMC after this patch:" not in prompt:
        errors.append("missing_post_patch_omc_transition")
    lowered = prompt.lower()
    for term in FORBIDDEN_HISTORY_TERMS:
        if term.lower() in lowered:
            errors.append(f"forbidden:{term}")
    return errors


def build_repair_history_contract_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    canonical_history = build_canonical_repair_history()
    prompt = _format_repair_history(canonical_history)
    validation_errors = validate_repair_history_prompt(prompt)
    summary = {
        "version": "v0.27.5",
        "status": "PASS" if not validation_errors else "REVIEW",
        "analysis_scope": "repair_history_transition_contract",
        "contract_scope": "raw_feedback_transition_only",
        "validation_errors": validation_errors,
        "contains_input_omc_summary": "OMC before this patch:" in prompt,
        "contains_post_patch_omc_summary": "OMC after this patch:" in prompt,
        "forbidden_terms": list(FORBIDDEN_HISTORY_TERMS),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "repair_history_transition_contract_ready"
            if not validation_errors
            else "repair_history_transition_contract_needs_review"
        ),
        "next_focus": "rerun_deepseek_source_backed_slice_with_transition_history",
    }
    write_outputs(out_dir=out_dir, summary=summary, canonical_history=canonical_history, prompt=prompt)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    canonical_history: list[dict[str, Any]],
    prompt: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_history.json").write_text(
        json.dumps(canonical_history, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "formatted_history.txt").write_text(prompt, encoding="utf-8")
