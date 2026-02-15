from __future__ import annotations

from .change_apply import validate_change_set
from .change_plan import validate_change_plan
from .intent import SUPPORTED_INTENTS

ALLOWED_PLANNER_OUTPUT_KEYS = {
    "intent",
    "proposal_id",
    "overrides",
    "change_plan",
    "change_set_draft",
    "planner",
    "planner_inputs",
    "context",
    "raw_response",
}

ALLOWED_PLANNER_OVERRIDE_KEYS = {
    "risk_level",
    "change_summary",
    "checkers",
    "checker_config",
    "change_set_path",
    "physical_invariants",
}


def validate_planner_output(payload: dict, *, strict_top_level: bool = True) -> None:
    if not isinstance(payload, dict):
        raise ValueError("planner output must be a JSON object")

    if strict_top_level:
        unknown = sorted(k for k in payload if k not in ALLOWED_PLANNER_OUTPUT_KEYS)
        if unknown:
            raise ValueError(f"planner output contains unsupported top-level keys: {unknown}")

    intent = payload.get("intent")
    if intent not in SUPPORTED_INTENTS:
        raise ValueError(f"intent must be one of {sorted(SUPPORTED_INTENTS)}")

    proposal_id = payload.get("proposal_id")
    if proposal_id is not None and (not isinstance(proposal_id, str) or not proposal_id.strip()):
        raise ValueError("proposal_id must be a non-empty string when provided")

    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be a JSON object")
    unknown_overrides = sorted(k for k in overrides if k not in ALLOWED_PLANNER_OVERRIDE_KEYS)
    if unknown_overrides:
        raise ValueError(f"overrides contain unsupported keys: {unknown_overrides}")

    for key in ("planner",):
        value = payload.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{key} must be a non-empty string when provided")
    for key in ("planner_inputs", "context", "raw_response"):
        value = payload.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"{key} must be a JSON object when provided")

    change_plan = payload.get("change_plan")
    if change_plan is not None:
        validate_change_plan(change_plan)

    change_set_draft = payload.get("change_set_draft")
    if change_set_draft is not None:
        validate_change_set(change_set_draft)
