from __future__ import annotations

from .agent_modelica_v0_10_0_common import PROXY_LEAKAGE_RISK_LEVELS, REAL_ORIGIN_DISTANCE_VALUES, SOURCE_ORIGIN_CLASSES
from .agent_modelica_v0_10_0_governance_pack import (
    ANTI_PROXY_LEAKAGE_AUDIT_SCHEMA,
    REAL_ORIGIN_AUTHENTICITY_AUDIT_SCHEMA,
)


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

    authenticity = (
        row.get("real_origin_authenticity_audit")
        if isinstance(row.get("real_origin_authenticity_audit"), dict)
        else {}
    )
    anti_proxy = row.get("anti_proxy_leakage_audit") if isinstance(row.get("anti_proxy_leakage_audit"), dict) else {}
    reasons.extend(_validate_schema_fields(authenticity, REAL_ORIGIN_AUTHENTICITY_AUDIT_SCHEMA, prefix="real_origin_authenticity_audit"))
    reasons.extend(_validate_schema_fields(anti_proxy, ANTI_PROXY_LEAKAGE_AUDIT_SCHEMA, prefix="anti_proxy_leakage_audit"))

    provenance = str(authenticity.get("source_provenance") or "").strip()
    source_origin_class = authenticity.get("source_origin_class")
    real_origin_distance = authenticity.get("real_origin_distance")
    workflow_legitimacy_pass = authenticity.get("workflow_legitimacy_pass")
    real_origin_authenticity_pass = authenticity.get("real_origin_authenticity_pass")
    authenticity_audit_pass = authenticity.get("real_origin_authenticity_audit_pass")

    if not provenance:
        reasons.append("reject_missing_source_provenance")
    if workflow_legitimacy_pass is False:
        reasons.append("reject_workflow_legitimacy_fail")
    if real_origin_authenticity_pass is False:
        reasons.append("reject_real_origin_authenticity_fail")
    if source_origin_class not in SOURCE_ORIGIN_CLASSES:
        reasons.append("reject_unknown_source_origin_class")
    if real_origin_distance not in REAL_ORIGIN_DISTANCE_VALUES:
        reasons.append("reject_unknown_real_origin_distance")
    if source_origin_class == "workflow_proximal_proxy":
        reasons.append("reject_workflow_proximal_proxy_class")
    if real_origin_distance == "far":
        reasons.append("reject_far_real_origin_distance")
    if source_origin_class == "real_origin" and real_origin_distance == "far":
        reasons.append("reject_internal_origin_distance_contradiction")

    expected_auth_pass = (
        bool(workflow_legitimacy_pass)
        and bool(real_origin_authenticity_pass)
        and source_origin_class != "workflow_proximal_proxy"
        and real_origin_distance != "far"
        and not (source_origin_class == "real_origin" and real_origin_distance == "far")
    )
    if bool(authenticity_audit_pass) != expected_auth_pass:
        reasons.append("reject_real_origin_authenticity_audit_incoherent")

    proxy_leakage_risk_level = anti_proxy.get("proxy_leakage_risk_level")
    if proxy_leakage_risk_level not in PROXY_LEAKAGE_RISK_LEVELS:
        reasons.append("reject_unknown_proxy_leakage_risk")
    if proxy_leakage_risk_level == "high":
        reasons.append("reject_high_proxy_leakage_risk")
    if anti_proxy.get("task_definition_depends_on_known_v0_8_or_v0_9_scaffolding") is True:
        reasons.append("reject_known_scaffolding_dependency")
    expected_anti_proxy_pass = (
        anti_proxy.get("task_definition_depends_on_known_v0_8_or_v0_9_scaffolding") is False
        and proxy_leakage_risk_level in {"low", "medium"}
    )
    if bool(anti_proxy.get("anti_proxy_leakage_audit_pass")) != expected_anti_proxy_pass:
        reasons.append("reject_anti_proxy_leakage_audit_incoherent")

    admitted = not reasons
    mainline_counted = admitted and source_origin_class == "real_origin" and real_origin_distance in {"near", "medium"}
    return {
        "task_id": row.get("task_id"),
        "admitted": admitted,
        "mainline_counted": mainline_counted,
        "source_origin_class": source_origin_class,
        "real_origin_distance": real_origin_distance,
        "family_id": row.get("family_id"),
        "source_id": row.get("source_id"),
        "rejection_reasons": reasons,
    }


def evaluate_candidate_rows(rows: list[dict]) -> list[dict]:
    return [evaluate_candidate_row(row) for row in rows if isinstance(row, dict)]
