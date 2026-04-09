from __future__ import annotations

from .agent_modelica_v0_9_0_common import CONTEXT_NATURALNESS_RISK_VALUES, PRIORITY_BARRIERS
from .agent_modelica_v0_9_0_governance_pack import AUTHENTICITY_AUDIT_SCHEMA, BARRIER_SAMPLING_AUDIT_SCHEMA


def _validate_schema_fields(obj: dict, schema: dict, *, prefix: str) -> list[str]:
    reasons: list[str] = []
    required_fields = schema.get("required_fields") if isinstance(schema.get("required_fields"), dict) else {}
    for field_name, rule in required_fields.items():
        if field_name not in obj:
            reasons.append(f"{prefix}.missing:{field_name}")
            continue
        value = obj.get(field_name)
        expected_type = rule.get("type")
        if expected_type == "bool" and not isinstance(value, bool):
            reasons.append(f"{prefix}.type:{field_name}")
        elif expected_type == "string" and not isinstance(value, str):
            reasons.append(f"{prefix}.type:{field_name}")
        elif expected_type == "enum":
            allowed_values = set(rule.get("allowed_values") or [])
            if value not in allowed_values:
                reasons.append(f"{prefix}.enum:{field_name}")
        if rule.get("non_empty") and isinstance(value, str) and not value.strip():
            reasons.append(f"{prefix}.empty:{field_name}")
    return reasons


def evaluate_candidate_row(row: dict) -> dict:
    reasons: list[str] = []
    for field_name in ("task_id", "source_id", "family_id", "workflow_task_template_id", "complexity_tier"):
        value = row.get(field_name)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"top_level_missing:{field_name}")

    authenticity = row.get("authenticity_audit") if isinstance(row.get("authenticity_audit"), dict) else {}
    sampling = row.get("barrier_sampling_audit") if isinstance(row.get("barrier_sampling_audit"), dict) else {}
    reasons.extend(_validate_schema_fields(authenticity, AUTHENTICITY_AUDIT_SCHEMA, prefix="authenticity_audit"))
    reasons.extend(_validate_schema_fields(sampling, BARRIER_SAMPLING_AUDIT_SCHEMA, prefix="barrier_sampling_audit"))

    provenance = str(authenticity.get("source_provenance") or "").strip()
    if not provenance:
        reasons.append("reject_missing_source_provenance")
    if authenticity.get("workflow_proximity_pass") is False:
        reasons.append("reject_workflow_proximity_fail")
    if authenticity.get("anti_fake_workflow_pass") is False:
        reasons.append("reject_anti_fake_workflow_fail")
    if authenticity.get("goal_level_acceptance_is_realistic") is False:
        reasons.append("reject_unrealistic_goal_acceptance")
    context_risk = authenticity.get("context_naturalness_risk")
    if context_risk not in CONTEXT_NATURALNESS_RISK_VALUES:
        reasons.append("reject_unknown_context_naturalness_risk")
    if context_risk == "high":
        reasons.append("reject_high_context_naturalness_risk")
    expected_auth_pass = (
        bool(authenticity.get("workflow_proximity_pass"))
        and bool(authenticity.get("anti_fake_workflow_pass"))
        and bool(authenticity.get("goal_level_acceptance_is_realistic"))
        and context_risk != "high"
    )
    if bool(authenticity.get("authenticity_audit_pass")) != expected_auth_pass:
        reasons.append("reject_authenticity_audit_incoherent")

    if sampling.get("task_definition_was_changed_for_barrier_targeting") is True:
        reasons.append("reject_barrier_targeting_changed_task_definition")
    intent_present = bool(sampling.get("barrier_sampling_intent_present"))
    target_barrier = str(sampling.get("target_barrier_family") or "")
    if intent_present and target_barrier not in PRIORITY_BARRIERS:
        reasons.append("reject_unknown_target_barrier_family")
    expected_sampling_pass = (
        not bool(sampling.get("task_definition_was_changed_for_barrier_targeting"))
        and (not intent_present or target_barrier in PRIORITY_BARRIERS)
    )
    if bool(sampling.get("barrier_sampling_audit_pass")) != expected_sampling_pass:
        reasons.append("reject_barrier_sampling_audit_incoherent")

    admitted = not reasons
    return {
        "task_id": row.get("task_id"),
        "admitted": admitted,
        "rejection_reasons": reasons,
        "target_barrier_family": target_barrier if intent_present else "",
    }


def evaluate_candidate_rows(rows: list[dict]) -> list[dict]:
    return [evaluate_candidate_row(row) for row in rows if isinstance(row, dict)]

