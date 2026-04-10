from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_0_common import (
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    PROMOTED_MAINLINE_MIN_COUNT,
    PROMOTED_MAINLINE_MIN_FAMILY_COUNT,
    PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT,
    PROXY_LEAKAGE_RISK_LEVELS,
    REAL_ORIGIN_DISTANCE_VALUES,
    SCHEMA_PREFIX,
    SOURCE_ORIGIN_CLASSES,
    load_json,
    now_utc,
    write_json,
    write_text,
)


REAL_ORIGIN_SOURCE_REGISTRY = [
    {
        "source_id": "open_source_issue_archive_buildings",
        "source_type": "repository_issue_workflow",
        "provenance_description": "Open-source issue-linked workflow maintenance demands extracted from Buildings and IBPSA model sources.",
        "source_origin_class": "real_origin",
        "expected_real_origin_distance": "near",
        "eligible_workflow_families": [
            "control_library_maintenance",
            "controller_reset_maintenance",
        ],
        "proxy_leakage_risk_note": "Low when task definitions stay grounded in issue-linked maintenance intent rather than v0.8/v0.9 scaffolding.",
    },
    {
        "source_id": "open_source_issue_archive_msl",
        "source_type": "repository_issue_workflow",
        "provenance_description": "Open-source issue-linked maintenance and conversion tasks extracted from Modelica Standard Library sources.",
        "source_origin_class": "real_origin",
        "expected_real_origin_distance": "medium",
        "eligible_workflow_families": [
            "multibody_constraint_maintenance",
            "conversion_compatibility_maintenance",
        ],
        "proxy_leakage_risk_note": "Medium because issue-linked extraction still requires normalization into workflow tasks.",
    },
    {
        "source_id": "semi_real_maintenance_digest",
        "source_type": "maintenance_record_digest",
        "provenance_description": "Semi-structured maintenance digest with workflow relevance but weaker direct issue-to-task traceability.",
        "source_origin_class": "semi_real_origin",
        "expected_real_origin_distance": "medium",
        "eligible_workflow_families": [
            "maintenance_regression_followup",
        ],
        "proxy_leakage_risk_note": "Allowed as a side bucket only; must not silently count as mainline real-origin.",
    },
    {
        "source_id": "v09_expanded_proxy_archive",
        "source_type": "workflow_proximal_proxy_archive",
        "provenance_description": "The v0.9.x expanded authentic workflow pool carried forward only as a proxy reference set.",
        "source_origin_class": "workflow_proximal_proxy",
        "expected_real_origin_distance": "far",
        "eligible_workflow_families": [
            "proxy_reference_only",
        ],
        "proxy_leakage_risk_note": "Quarantine source; never admissible as mainline real-origin evidence.",
    },
]

REAL_ORIGIN_AUTHENTICITY_AUDIT_SCHEMA = {
    "required_fields": {
        "source_provenance": {"type": "string", "non_empty": True},
        "source_origin_class": {"type": "enum", "allowed_values": list(SOURCE_ORIGIN_CLASSES)},
        "real_origin_distance": {"type": "enum", "allowed_values": list(REAL_ORIGIN_DISTANCE_VALUES)},
        "workflow_legitimacy_pass": {"type": "bool"},
        "real_origin_authenticity_pass": {"type": "bool"},
        "real_origin_authenticity_audit_pass": {"type": "bool"},
    },
    "interpretation_rules": [
        "real_origin_authenticity_audit_pass is allowed only when workflow_legitimacy_pass and real_origin_authenticity_pass are both true.",
        "source_origin_class = workflow_proximal_proxy forces real_origin_authenticity_audit_pass = false.",
        "real_origin_distance = far forces real_origin_authenticity_audit_pass = false.",
        "source_origin_class = real_origin with real_origin_distance = far is an internal contradiction and must fail audit.",
    ],
}

ANTI_PROXY_LEAKAGE_AUDIT_SCHEMA = {
    "required_fields": {
        "proxy_leakage_risk_present": {"type": "bool"},
        "proxy_leakage_risk_level": {"type": "enum", "allowed_values": list(PROXY_LEAKAGE_RISK_LEVELS)},
        "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": {"type": "string", "non_empty": True},
        "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": {"type": "bool"},
        "anti_proxy_leakage_audit_pass": {"type": "bool"},
    },
    "interpretation_rules": [
        "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding = true forces anti_proxy_leakage_audit_pass = false.",
        "proxy_leakage_risk_level = high forces anti_proxy_leakage_audit_pass = false.",
    ],
}

CANDIDATE_REJECTION_RULES = [
    {"rule_id": "reject_missing_source_provenance", "description": "source provenance missing"},
    {"rule_id": "reject_workflow_legitimacy_fail", "description": "workflow legitimacy audit failed"},
    {"rule_id": "reject_real_origin_authenticity_fail", "description": "real-origin authenticity failed"},
    {"rule_id": "reject_workflow_proximal_proxy_class", "description": "workflow_proximal_proxy cannot enter the mainline candidate pool"},
    {"rule_id": "reject_far_real_origin_distance", "description": "real_origin_distance = far"},
    {"rule_id": "reject_internal_origin_distance_contradiction", "description": "real_origin source cannot simultaneously be far-distance"},
    {"rule_id": "reject_high_proxy_leakage_risk", "description": "proxy_leakage_risk_level = high"},
    {"rule_id": "reject_known_scaffolding_dependency", "description": "task definition depends on known v0.8/v0.9 scaffolding"},
]

REAL_ORIGIN_AUTHENTICITY_GUARD_DEFINITION = {
    "guard_name": "real_origin_authenticity_guard_definition",
    "bound_skill": "Real-Origin Evaluation Governance Pattern",
    "proxy_laundering_allowed": False,
    "semi_real_origin_mainline_allowed": False,
    "promoted_mainline_min_count": PROMOTED_MAINLINE_MIN_COUNT,
    "promoted_mainline_min_family_count": PROMOTED_MAINLINE_MIN_FAMILY_COUNT,
    "promoted_max_single_source_share_pct": PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT,
    "guardrail_statement": "Real-origin evaluation may widen the source base only through explicit provenance and anti-proxy discipline.",
}

SOURCE_TYPE_PLACEHOLDERS = [
    "repository_issue_workflow",
    "maintenance_change_record",
    "regression_failure_record",
]


def build_seed_candidate_rows() -> list[dict]:
    return [
        {
            "task_id": "v1000_buildings_issue_510_restore_pid_assertion_tolerance",
            "source_id": "open_source_issue_archive_buildings",
            "source_record_id": "buildings_issue_510",
            "family_id": "control_library_maintenance",
            "workflow_task_template_id": "restore_controller_assertion_behavior",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "Buildings issue 510 referenced in LimPID_e449ee5000.mo revisions",
                "source_origin_class": "real_origin",
                "real_origin_distance": "near",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": False,
                "proxy_leakage_risk_level": "low",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The task is grounded in an issue-linked controller maintenance demand rather than a v0.8/v0.9 workflow wrapper.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_ibpsa_issue_540_restore_reset_controller_type_path",
            "source_id": "open_source_issue_archive_buildings",
            "source_record_id": "ibpsa_issue_540",
            "family_id": "controller_reset_maintenance",
            "workflow_task_template_id": "restore_controller_reset_chain",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "IBPSA issue 540 referenced in LimPIDWithReset_03ab422590.mo revisions",
                "source_origin_class": "real_origin",
                "real_origin_distance": "near",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": False,
                "proxy_leakage_risk_level": "low",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The task comes from an upstream maintenance issue about a concrete controller-reset implementation path.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_msl_issue_951_restore_multibody_gear_constraint_test",
            "source_id": "open_source_issue_archive_msl",
            "source_record_id": "msl_issue_951",
            "family_id": "multibody_constraint_maintenance",
            "workflow_task_template_id": "restore_multibody_constraint_behavior",
            "complexity_tier": "complex",
            "real_origin_authenticity_audit": {
                "source_provenance": "MSL issue 951 referenced in ModelicaTest.MultiBody.GearConstraint4 documentation",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "This task still requires extraction from a test-model issue reference, but the demand is issue-originated rather than synthesized from v0.9.x artifacts.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_msl_issue_813_restore_conversion_chain_case",
            "source_id": "open_source_issue_archive_msl",
            "source_record_id": "msl_issue_813",
            "family_id": "conversion_compatibility_maintenance",
            "workflow_task_template_id": "restore_conversion_compatibility",
            "complexity_tier": "simple",
            "real_origin_authenticity_audit": {
                "source_provenance": "MSL issue 813 referenced in ModelicaTestConversion4 conversion tests",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The task is issue-linked but still requires normalization from conversion-test context into a workflow demand.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_msl_issue_1724_restore_conversion_chain_case",
            "source_id": "open_source_issue_archive_msl",
            "source_record_id": "msl_issue_1724",
            "family_id": "conversion_compatibility_maintenance",
            "workflow_task_template_id": "restore_conversion_compatibility",
            "complexity_tier": "simple",
            "real_origin_authenticity_audit": {
                "source_provenance": "MSL issue 1724 referenced in ModelicaTestConversion4 conversion tests",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The task is still extractive, but the issue reference makes its real-origin chain explicit.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_msl_issue_2441_restore_conversion_chain_case",
            "source_id": "open_source_issue_archive_msl",
            "source_record_id": "msl_issue_2441",
            "family_id": "conversion_compatibility_maintenance",
            "workflow_task_template_id": "restore_conversion_compatibility",
            "complexity_tier": "simple",
            "real_origin_authenticity_audit": {
                "source_provenance": "MSL issue 2441 referenced in ModelicaTestConversion4 conversion tests",
                "source_origin_class": "real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The issue-driven conversion context is real-origin enough to record, though not as clean as direct demand records.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_semi_real_maintenance_digest_followup",
            "source_id": "semi_real_maintenance_digest",
            "source_record_id": "maintenance_digest_followup_01",
            "family_id": "maintenance_regression_followup",
            "workflow_task_template_id": "restore_maintenance_followup_behavior",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "Semi-structured maintenance digest synthesized from multiple open-source maintenance notes",
                "source_origin_class": "semi_real_origin",
                "real_origin_distance": "medium",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": True,
                "real_origin_authenticity_audit_pass": True,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "medium",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "This row is still grounded in maintenance traces, but its aggregation layer keeps it in the side bucket.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                "anti_proxy_leakage_audit_pass": True,
            },
        },
        {
            "task_id": "v1000_v09_proxy_reference_row",
            "source_id": "v09_expanded_proxy_archive",
            "source_record_id": "v09_proxy_reference_01",
            "family_id": "proxy_reference_only",
            "workflow_task_template_id": "proxy_reference_only",
            "complexity_tier": "medium",
            "real_origin_authenticity_audit": {
                "source_provenance": "v0.9 expanded authentic workflow pool carried only as a proxy reference archive",
                "source_origin_class": "workflow_proximal_proxy",
                "real_origin_distance": "far",
                "workflow_legitimacy_pass": True,
                "real_origin_authenticity_pass": False,
                "real_origin_authenticity_audit_pass": False,
            },
            "anti_proxy_leakage_audit": {
                "proxy_leakage_risk_present": True,
                "proxy_leakage_risk_level": "high",
                "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "This row explicitly depends on known v0.9 scaffolding and exists only to prove rejection behavior.",
                "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": True,
                "anti_proxy_leakage_audit_pass": False,
            },
        },
    ]


def build_v1000_governance_pack(
    *,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    candidate_rows = build_seed_candidate_rows()
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_governance_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "bound_skill": "Real-Origin Evaluation Governance Pattern",
        "real_origin_source_registry": REAL_ORIGIN_SOURCE_REGISTRY,
        "real_origin_source_type_placeholders": SOURCE_TYPE_PLACEHOLDERS,
        "real_origin_authenticity_audit_schema": REAL_ORIGIN_AUTHENTICITY_AUDIT_SCHEMA,
        "anti_proxy_leakage_audit_schema": ANTI_PROXY_LEAKAGE_AUDIT_SCHEMA,
        "candidate_rejection_rules": CANDIDATE_REJECTION_RULES,
        "real_origin_authenticity_guard_definition": REAL_ORIGIN_AUTHENTICITY_GUARD_DEFINITION,
        "baseline_candidate_rows": candidate_rows,
        "real_origin_candidate_pool_total_count": len(candidate_rows),
    }
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "governance_pack.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.0 Governance Pack",
                "",
                f"- real_origin_candidate_pool_total_count: `{len(candidate_rows)}`",
                f"- promoted_mainline_min_count: `{PROMOTED_MAINLINE_MIN_COUNT}`",
                f"- promoted_mainline_min_family_count: `{PROMOTED_MAINLINE_MIN_FAMILY_COUNT}`",
                f"- promoted_max_single_source_share_pct: `{PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.0 governance pack artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v1000_governance_pack(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "real_origin_candidate_pool_total_count": payload.get("real_origin_candidate_pool_total_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
