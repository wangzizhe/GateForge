from __future__ import annotations

from datetime import datetime, timezone


STEP_SCHEMA_VERSION = "agent_modelica_v0_3_14_step_experience"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: object) -> str:
    return str(value or "").strip()


def action_type_from_row(*, attempt_field: str, action_key: str, rule_id: str) -> str:
    key = norm(action_key)
    if "|" in key:
        parts = [part.strip() for part in key.split("|") if part.strip()]
        if len(parts) >= 2:
            return parts[1]
    rid = norm(rule_id)
    if rid.startswith("rule_"):
        return rid[len("rule_") :]
    field_name = norm(attempt_field)
    return field_name or rid or "unknown_action"


def residual_signal_cluster(
    *,
    dominant_stage_subtype: str,
    error_subtype: str = "",
    observed_failure_type: str = "",
    reason: str = "",
) -> str:
    stage = norm(dominant_stage_subtype)
    subtype = norm(error_subtype)
    observed = norm(observed_failure_type)
    cause = norm(reason)
    if stage and subtype and subtype.lower() not in {"none", "unknown"}:
        return f"{stage}|{subtype}"
    if stage and observed and observed.lower() not in {"none", "unknown"}:
        return f"{stage}|{observed}"
    if stage:
        return stage
    if observed and cause:
        return f"{observed}|{cause}"
    return observed or cause or "unknown_residual_signal"


def bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None

