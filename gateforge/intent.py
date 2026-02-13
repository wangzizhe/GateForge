from __future__ import annotations

from .change_apply import validate_change_set
from .change_plan import validate_change_plan

SUPPORTED_INTENTS = {
    "demo_mock_pass",
    "demo_openmodelica_pass",
    "medium_openmodelica_pass",
    "runtime_regress_low_risk",
    "runtime_regress_high_risk",
}


def validate_intent_request(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("intent payload must be a JSON object")
    intent = payload.get("intent")
    if intent not in SUPPORTED_INTENTS:
        raise ValueError(f"intent must be one of {sorted(SUPPORTED_INTENTS)}")

    proposal_id = payload.get("proposal_id")
    if proposal_id is not None and (not isinstance(proposal_id, str) or not proposal_id.strip()):
        raise ValueError("proposal_id must be a non-empty string when provided")

    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be a JSON object")

    change_plan = payload.get("change_plan")
    if change_plan is not None:
        validate_change_plan(change_plan)

    change_set_draft = payload.get("change_set_draft")
    if change_set_draft is not None:
        validate_change_set(change_set_draft)

