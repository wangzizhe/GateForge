from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "observation_contract_v0_26_1"
OBSERVATION_CONTRACT_VERSION = "agent_modelica_observation_contract_v1"

REQUIRED_OBSERVATION_FIELDS = (
    "schema_version",
    "run_id",
    "case_id",
    "repair_round_index",
    "model_text",
    "workflow_goal",
    "raw_omc_feedback",
    "raw_simulation_feedback",
    "raw_behavioral_oracle_feedback",
    "previous_patch_summary",
    "provider_name",
    "model_profile",
)

FORBIDDEN_OBSERVATION_FIELDS = (
    "root_cause_hint",
    "repair_hint",
    "expected_fix",
    "target_patch",
    "oracle_private_answer",
    "selected_candidate_id",
    "candidate_score",
    "deterministic_diagnosis",
    "routing_decision",
)


def observation_contract_schema() -> dict[str, Any]:
    return {
        "schema_version": OBSERVATION_CONTRACT_VERSION,
        "required_fields": list(REQUIRED_OBSERVATION_FIELDS),
        "forbidden_fields": list(FORBIDDEN_OBSERVATION_FIELDS),
        "allowed_feedback_policy": {
            "raw_omc_feedback": "raw compiler output or empty string",
            "raw_simulation_feedback": "raw simulation output or empty string",
            "raw_behavioral_oracle_feedback": "raw oracle output or empty string",
            "previous_patch_summary": "descriptive summary of prior LLM patch, not a repair hint",
        },
        "provider_agnostic": True,
        "executor_decision_allowed": False,
    }


def build_observation_event(
    *,
    run_id: str,
    case_id: str,
    repair_round_index: int,
    model_text: str,
    workflow_goal: str,
    raw_omc_feedback: str = "",
    raw_simulation_feedback: str = "",
    raw_behavioral_oracle_feedback: str = "",
    previous_patch_summary: str = "",
    provider_name: str = "",
    model_profile: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": OBSERVATION_CONTRACT_VERSION,
        "run_id": str(run_id),
        "case_id": str(case_id),
        "repair_round_index": int(repair_round_index),
        "model_text": str(model_text),
        "workflow_goal": str(workflow_goal),
        "raw_omc_feedback": str(raw_omc_feedback),
        "raw_simulation_feedback": str(raw_simulation_feedback),
        "raw_behavioral_oracle_feedback": str(raw_behavioral_oracle_feedback),
        "previous_patch_summary": str(previous_patch_summary),
        "provider_name": str(provider_name),
        "model_profile": str(model_profile),
    }


def validate_observation_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_OBSERVATION_FIELDS:
        if field not in event:
            errors.append(f"missing:{field}")
    for field in FORBIDDEN_OBSERVATION_FIELDS:
        if field in event:
            errors.append(f"forbidden:{field}")
    if event.get("schema_version") != OBSERVATION_CONTRACT_VERSION:
        errors.append("schema_version_mismatch")
    try:
        repair_round_index = int(event.get("repair_round_index"))
    except Exception:
        errors.append("repair_round_index_must_be_int")
    else:
        if repair_round_index < 1:
            errors.append("repair_round_index_must_be_positive")
    for field in (
        "model_text",
        "workflow_goal",
        "raw_omc_feedback",
        "raw_simulation_feedback",
        "raw_behavioral_oracle_feedback",
        "previous_patch_summary",
    ):
        if field in event and not isinstance(event.get(field), str):
            errors.append(f"{field}_must_be_string")
    return errors


def build_observation_contract_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    canonical_event = build_observation_event(
        run_id="contract_smoke",
        case_id="observation_contract_smoke",
        repair_round_index=1,
        model_text="model Demo\nend Demo;",
        workflow_goal="Repair the Modelica model so it checks successfully.",
        raw_omc_feedback="model_check_error",
        raw_simulation_feedback="",
        raw_behavioral_oracle_feedback="",
        previous_patch_summary="",
        provider_name="deepseek",
        model_profile="deepseek-v4-flash",
    )
    validation_errors = validate_observation_event(canonical_event)
    summary = {
        "version": "v0.26.1",
        "status": "PASS" if not validation_errors else "REVIEW",
        "analysis_scope": "observation_contract",
        "contract_version": OBSERVATION_CONTRACT_VERSION,
        "schema": observation_contract_schema(),
        "canonical_event_validation_errors": validation_errors,
        "provider_agnostic": True,
        "observation_contains_hidden_hint": False,
        "executor_changes": "none",
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
            "public_changelog_update": "defer_until_public_phase_closeout",
        },
        "decision": (
            "observation_contract_ready_for_run_mode_matrix"
            if not validation_errors
            else "observation_contract_needs_review"
        ),
        "next_focus": "v0.26.2_provider_adapter_model_profile_matrix",
    }
    write_outputs(out_dir=out_dir, summary=summary, canonical_event=canonical_event)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], canonical_event: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "schema.json").write_text(
        json.dumps(observation_contract_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "canonical_event.json").write_text(
        json.dumps(canonical_event, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
