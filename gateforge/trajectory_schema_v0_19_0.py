from __future__ import annotations

SCHEMA_VERSION_TURN = "trajectory_turn_v0_19_0"
SCHEMA_VERSION_SUMMARY = "trajectory_summary_v0_19_0"

VALID_SIMULATION_STATUSES = frozenset({"PASS", "FAIL", "ERROR"})
VALID_TURN_OUTCOMES = frozenset({
    "success",
    "partial_progress",
    "no_progress",
    "stalled",
    "gave_up",
})
VALID_TERMINATION_REASONS = frozenset({"success", "timeout", "stalled", "cycling"})
VALID_FINAL_OUTCOMES = frozenset({"success", "failure"})

TURN_RECORD_REQUIRED_FIELDS = frozenset({
    "schema_version",
    "task_id",
    "turn_id",
    "prompt",
    "llm_response",
    "execution",
    "turn_outcome",
})

SUMMARY_RECORD_REQUIRED_FIELDS = frozenset({
    "schema_version",
    "task_id",
    "total_turns",
    "termination_reason",
    "final_outcome",
    "progressive_solve",
    "turn_outcomes",
})


def validate_turn_record(record: dict) -> list[str]:
    """Returns a list of validation errors; empty list means valid."""
    errors: list[str] = []

    for field in TURN_RECORD_REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")

    if record.get("schema_version") != SCHEMA_VERSION_TURN:
        errors.append(f"schema_version must be '{SCHEMA_VERSION_TURN}'")

    execution = record.get("execution") or {}
    sim_status = execution.get("simulation_status")
    if sim_status not in VALID_SIMULATION_STATUSES:
        errors.append(f"execution.simulation_status must be one of {VALID_SIMULATION_STATUSES}")

    turn_outcome = record.get("turn_outcome")
    if turn_outcome not in VALID_TURN_OUTCOMES:
        errors.append(f"turn_outcome must be one of {VALID_TURN_OUTCOMES}")

    prompt = record.get("prompt") or {}
    if not isinstance(prompt.get("system"), str) or not isinstance(prompt.get("user"), str):
        errors.append("prompt must have 'system' and 'user' string fields")

    llm_response = record.get("llm_response") or {}
    if not isinstance(llm_response.get("raw"), str):
        errors.append("llm_response.raw must be a string (full untruncated response)")

    return errors


def compute_progressive_solve(turn_outcomes: list[str], final_outcome: str) -> bool:
    """Returns True when all three conditions hold:
    1. final_outcome is 'success'
    2. at least one intermediate turn has outcome 'partial_progress'
    3. the first turn outcome is not 'success' (not fixed by rule alone in turn 1)
    """
    if final_outcome != "success":
        return False
    if not turn_outcomes:
        return False
    if turn_outcomes[0] == "success":
        return False
    return "partial_progress" in turn_outcomes


def validate_summary_record(record: dict) -> list[str]:
    """Returns a list of validation errors; empty list means valid."""
    errors: list[str] = []

    for field in SUMMARY_RECORD_REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"missing required field: {field}")

    if record.get("schema_version") != SCHEMA_VERSION_SUMMARY:
        errors.append(f"schema_version must be '{SCHEMA_VERSION_SUMMARY}'")

    termination_reason = record.get("termination_reason")
    if termination_reason not in VALID_TERMINATION_REASONS:
        errors.append(f"termination_reason must be one of {VALID_TERMINATION_REASONS}")

    final_outcome = record.get("final_outcome")
    if final_outcome not in VALID_FINAL_OUTCOMES:
        errors.append(f"final_outcome must be one of {VALID_FINAL_OUTCOMES}")

    turn_outcomes = record.get("turn_outcomes")
    if not isinstance(turn_outcomes, list):
        errors.append("turn_outcomes must be a list")

    # verify progressive_solve matches computed value
    if isinstance(turn_outcomes, list) and final_outcome in VALID_FINAL_OUTCOMES:
        expected = compute_progressive_solve(turn_outcomes, final_outcome)
        if record.get("progressive_solve") != expected:
            errors.append(
                f"progressive_solve should be {expected} given turn_outcomes={turn_outcomes} "
                f"and final_outcome={final_outcome}"
            )

    return errors


__all__ = [
    "SCHEMA_VERSION_SUMMARY",
    "SCHEMA_VERSION_TURN",
    "SUMMARY_RECORD_REQUIRED_FIELDS",
    "TURN_RECORD_REQUIRED_FIELDS",
    "VALID_FINAL_OUTCOMES",
    "VALID_SIMULATION_STATUSES",
    "VALID_TERMINATION_REASONS",
    "VALID_TURN_OUTCOMES",
    "compute_progressive_solve",
    "validate_summary_record",
    "validate_turn_record",
]
