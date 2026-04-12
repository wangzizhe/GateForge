from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_13_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_RUNTIME_STACK_IDENTITY,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V123_CLOSEOUT_PATH,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V115_DOMINANT_GAP_FAMILY,
    EXPECTED_V115_FORMAL_LABEL,
    EXPECTED_V123_CAVEAT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_mainline_anchor": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_capability_evaluation_reason": True,
    "named_reasons": [
        "capability_specific_compatibility_constraint",
        "bounded_instrumentation_need",
        "explicit_runtime_safety_sandboxing_requirement",
    ],
    "one_to_one_traceability_required": True,
    "broad_resampling_from_wider_pool_forbidden": True,
    "silent_case_replacement_forbidden": True,
}

DEFAULT_LEVER_MAP = {
    "planner_reasoning_depth_improvement": {
        "family_name": "planner_reasoning_depth_improvement",
        "concrete_change_surface": "merged_into_capability_level_execution_strategy_improvement",
        "gateforge_layer": "L2_planner",
        "in_scope_status": "merged",
        "named_reason_if_deferred": "overlaps_with_execution_strategy_surface_and_requires_merge_before_admission",
    },
    "search_control_and_replan_improvement": {
        "family_name": "search_control_and_replan_improvement",
        "concrete_change_surface": "L2_replan_policy_and_search_order_control",
        "gateforge_layer": "L2_replan",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "failure_state_diagnosis_improvement": {
        "family_name": "failure_state_diagnosis_improvement",
        "concrete_change_surface": "L3_L4_failure_bucket_and_diagnosis_chain_enrichment",
        "gateforge_layer": "L3_L4_diagnosis",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "capability_level_context_use_improvement": {
        "family_name": "capability_level_context_use_improvement",
        "concrete_change_surface": "L2_context_selection_and_prompt_contract_use",
        "gateforge_layer": "L2_context_contract_use",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "capability_level_execution_strategy_improvement": {
        "family_name": "capability_level_execution_strategy_improvement",
        "concrete_change_surface": "L2_planner_structured_plan_and_execution_strategy_upgrade",
        "gateforge_layer": "L2_planner",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
}

DEFAULT_FAMILY_SEPARATION_RULE = {
    "overlap_pairs_checked": [
        "planner_reasoning_depth_improvement::capability_level_execution_strategy_improvement",
    ],
    "merged_family_table": [
        {
            "source_family": "planner_reasoning_depth_improvement",
            "merged_into": "capability_level_execution_strategy_improvement",
            "reason": "same_L2_planner_behavior_surface",
        }
    ],
    "strict_separation_table": [
        {
            "family_name": "search_control_and_replan_improvement",
            "distinguished_from": "capability_level_execution_strategy_improvement",
            "rule": "must target replan policy or search ordering rather than static L2 planner prompt structure",
        },
        {
            "family_name": "failure_state_diagnosis_improvement",
            "distinguished_from": "capability_level_context_use_improvement",
            "rule": "must target diagnosis-chain interpretation rather than prompt-context shaping",
        },
    ],
    "family_separation_status": "ready",
}

DEFAULT_INTERVENTION_REGISTRY = {
    "intervention_rows": [
        {
            "intervention_id": "bounded_execution_strategy_upgrade_v1",
            "intervention_family": "capability_level_execution_strategy_improvement",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "shallow_multistep_planner_strategy_on_carried_product_gap_cases",
            "expected_effect_type": "mainline_workflow_improvement",
            "bounded_change_surface": "L2_structured_plan_and_execution_strategy_upgrade",
            "carried_baseline_reference": "v0_12_x_same_12_case_product_gap_baseline",
            "admission_status": "admitted",
        },
        {
            "intervention_id": "bounded_replan_search_control_upgrade_v1",
            "intervention_family": "search_control_and_replan_improvement",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "insufficient_branch_switch_or_search_reallocation_after_stall",
            "expected_effect_type": "mainline_workflow_improvement",
            "bounded_change_surface": "L2_replan_policy_and_search_budget_control_upgrade",
            "carried_baseline_reference": "v0_12_x_same_12_case_product_gap_baseline",
            "admission_status": "admitted",
        },
        {
            "intervention_id": "bounded_failure_diagnosis_upgrade_v1",
            "intervention_family": "failure_state_diagnosis_improvement",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "underpowered_failure_state_diagnosis_on_unresolved_cases",
            "expected_effect_type": "mainline_workflow_improvement",
            "bounded_change_surface": "L3_L4_failure_bucket_and_diagnosis_chain_upgrade",
            "carried_baseline_reference": "v0_12_x_same_12_case_product_gap_baseline",
            "admission_status": "admitted",
        },
        {
            "intervention_id": "broad_model_family_replacement_candidate",
            "intervention_family": "capability_level_execution_strategy_improvement",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "global_underpowered_model_behavior",
            "expected_effect_type": "mainline_workflow_improvement",
            "bounded_change_surface": "full_model_family_replacement",
            "carried_baseline_reference": "none",
            "admission_status": "rejected",
            "rejection_reason": "broad_model_family_replacement_out_of_scope",
        },
    ]
}

DEFAULT_COMPARISON_PROTOCOL = {
    "comparison_mode": "pre_vs_post_on_same_cases",
    "baseline_execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
    "post_intervention_execution_source_requirement": CURRENT_MAIN_EXECUTION_CHAIN,
    "same_case_requirement": True,
    "runtime_measurement_required": True,
    "mainline_vs_side_evidence_rule": "Mainline improvement requires workflow-outcome movement on the carried same-case baseline; side-evidence-only or token-only motion cannot be upgraded into mainline improvement.",
    "pre_post_capability_comparison_protocol_frozen": True,
}


def _build_baseline_anchor(*, v112_closeout_path: str, v115_closeout_path: str, v123_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    v112_builder = v112.get("product_gap_substrate_builder", {})
    v115_conclusion = load_json(v115_closeout_path).get("conclusion", {})
    v123_conclusion = load_json(v123_closeout_path).get("conclusion", {})
    substrate_table = v112_builder.get("product_gap_candidate_table") or []
    substrate_identity = v112_builder.get("carried_baseline_source", "")
    return {
        "baseline_product_gap_substrate_version": "v0_11_2",
        "baseline_phase_closeout_version": "v0_11_7",
        "baseline_operational_remedy_phase_closeout_version": "v0_12_3",
        "baseline_product_gap_substrate_identity": substrate_identity,
        "baseline_product_gap_formal_label": v115_conclusion.get("formal_adjudication_label"),
        "baseline_operational_remedy_caveat_label": v123_conclusion.get("explicit_caveat_label"),
        "baseline_blocker_readout": "residual_core_capability_gap_requires_capability_level_improvement_not_shell_hardening",
        "baseline_substrate_size": len(substrate_table),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION
            and len(substrate_table) == EXPECTED_V112_SUBSTRATE_SIZE
            and v115_conclusion.get("formal_adjudication_label") == EXPECTED_V115_FORMAL_LABEL
            and v115_conclusion.get("dominant_gap_family_readout") == EXPECTED_V115_DOMINANT_GAP_FAMILY
            and v123_conclusion.get("explicit_caveat_label") == EXPECTED_V123_CAVEAT
        ),
    }


def _build_baseline_continuity_check(*, v112_closeout_path: str, continuity_check_mode: str) -> dict:
    v112 = load_json(v112_closeout_path)
    builder = v112.get("product_gap_substrate_builder", {})
    rows = builder.get("product_gap_candidate_table") or []
    named_breakage_table: list[dict] = []
    for idx, row in enumerate(rows):
        missing_fields = [
            field
            for field in [
                "task_id",
                "source_id",
                "family_id",
                "workflow_task_template_id",
                "product_gap_scaffold_version",
                "product_gap_protocol_contract_version",
            ]
            if row.get(field) in (None, "", [])
        ]
        if missing_fields:
            named_breakage_table.append(
                {
                    "row_index": idx,
                    "task_id": row.get("task_id", ""),
                    "missing_fields": missing_fields,
                }
            )
    expected_mode = continuity_check_mode in {"schema_only", "live_dry_run", "full_live_rerun"}
    continuity_breakage_count = len(named_breakage_table)
    status = "ready" if expected_mode and len(rows) == EXPECTED_V112_SUBSTRATE_SIZE and continuity_breakage_count == 0 else "broken"
    return {
        "baseline_continuity_check_status": status,
        "carried_case_count": len(rows),
        "continuity_runtime_stack_identity": CURRENT_RUNTIME_STACK_IDENTITY,
        "continuity_check_mode": continuity_check_mode,
        "continuity_breakage_count": continuity_breakage_count,
        "named_breakage_table": named_breakage_table,
    }


def _validate_lever_map(lever_map: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    for family_name, row in lever_map.items():
        if not isinstance(row, dict):
            missing.append(f"{family_name}.object")
            continue
        for field in ["family_name", "concrete_change_surface", "gateforge_layer", "in_scope_status"]:
            if row.get(field) in (None, "", []):
                missing.append(f"{family_name}.{field}")
    return ("ready" if not missing else "partial", missing)


def _validate_family_separation(rule: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    if not rule.get("overlap_pairs_checked"):
        missing.append("overlap_pairs_checked")
    if not rule.get("merged_family_table"):
        missing.append("merged_family_table")
    if not rule.get("strict_separation_table"):
        missing.append("strict_separation_table")
    status = rule.get("family_separation_status")
    if status not in {"ready", "partial"}:
        missing.append("family_separation_status")
    return ("ready" if not missing and status == "ready" else "partial", missing)


def _validate_intervention_registry(registry: dict, lever_map: dict) -> tuple[dict, list[dict]]:
    rows = registry.get("intervention_rows") or []
    admitted = []
    rejected = []
    missing: list[str] = []
    merged_families = {
        name for name, row in lever_map.items() if row.get("in_scope_status") == "merged"
    }
    for row in rows:
        if not isinstance(row, dict):
            missing.append("row.object")
            continue
        for field in [
            "intervention_id",
            "intervention_family",
            "target_gap_family",
            "target_failure_mode",
            "expected_effect_type",
            "bounded_change_surface",
            "carried_baseline_reference",
            "admission_status",
        ]:
            if row.get(field) in (None, "", []):
                missing.append(f"{row.get('intervention_id', 'unknown')}.{field}")
        family = row.get("intervention_family")
        if family in merged_families and row.get("admission_status") == "admitted":
            missing.append(f"{row.get('intervention_id', 'unknown')}.merged_family_admitted")
        if lever_map.get(family, {}).get("in_scope_status") == "deferred" and row.get("admission_status") == "admitted":
            missing.append(f"{row.get('intervention_id', 'unknown')}.deferred_family_admitted")
        if row.get("admission_status") == "admitted":
            admitted.append(row)
        elif row.get("admission_status") == "rejected":
            rejected.append(row)
            if not row.get("rejection_reason"):
                missing.append(f"{row.get('intervention_id', 'unknown')}.rejection_reason")
    return {
        "intervention_registry_status": "frozen" if not missing and admitted else "partial",
        "admitted_intervention_count": len(admitted),
        "rejected_intervention_count": len(rejected),
        "named_first_intervention_pack_ids": [row["intervention_id"] for row in admitted],
        "admitted_rows": admitted,
        "rejected_rows": rejected,
        "rejection_reason_table": [
            {"intervention_id": row.get("intervention_id", ""), "rejection_reason": row.get("rejection_reason", "")}
            for row in rejected
        ],
        "missing_fields": missing,
    }, admitted


def _validate_comparison_protocol(protocol: dict) -> tuple[bool, list[str]]:
    missing = []
    if protocol.get("comparison_mode") != "pre_vs_post_on_same_cases":
        missing.append("comparison_mode")
    if protocol.get("baseline_execution_source") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("baseline_execution_source")
    if protocol.get("post_intervention_execution_source_requirement") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("post_intervention_execution_source_requirement")
    if not bool(protocol.get("same_case_requirement")):
        missing.append("same_case_requirement")
    if not bool(protocol.get("runtime_measurement_required")):
        missing.append("runtime_measurement_required")
    if not bool(protocol.get("pre_post_capability_comparison_protocol_frozen")):
        missing.append("pre_post_capability_comparison_protocol_frozen")
    return (not missing, missing)


def build_v130_governance_pack(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v123_closeout_path: str = str(DEFAULT_V123_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    lever_map: dict | None = None,
    family_separation_rule: dict | None = None,
    intervention_registry: dict | None = None,
    comparison_protocol: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    baseline_anchor = _build_baseline_anchor(
        v112_closeout_path=v112_closeout_path,
        v115_closeout_path=v115_closeout_path,
        v123_closeout_path=v123_closeout_path,
    )
    continuity_check = _build_baseline_continuity_check(
        v112_closeout_path=v112_closeout_path,
        continuity_check_mode=continuity_check_mode,
    )
    lever_map_payload = copy.deepcopy(lever_map or DEFAULT_LEVER_MAP)
    family_separation_payload = copy.deepcopy(family_separation_rule or DEFAULT_FAMILY_SEPARATION_RULE)
    registry_payload = copy.deepcopy(intervention_registry or DEFAULT_INTERVENTION_REGISTRY)
    comparison_protocol_payload = copy.deepcopy(comparison_protocol or DEFAULT_COMPARISON_PROTOCOL)

    lever_map_status, lever_map_missing = _validate_lever_map(lever_map_payload)
    family_separation_status, family_separation_missing = _validate_family_separation(family_separation_payload)
    registry_summary, admitted_rows = _validate_intervention_registry(registry_payload, lever_map_payload)
    comparison_protocol_ready, comparison_protocol_missing = _validate_comparison_protocol(comparison_protocol_payload)

    capability_intervention_admission_rules_frozen = registry_summary["intervention_registry_status"] == "frozen"
    named_first_intervention_pack_ready = bool(admitted_rows)
    minimum_completion_signal_pass = all(
        [
            registry_summary["intervention_registry_status"] == "frozen",
            capability_intervention_admission_rules_frozen,
            comparison_protocol_ready,
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            all(
                row.get("target_gap_family") and row.get("expected_effect_type")
                for row in admitted_rows
            ),
        ]
    )
    governance_ready_for_runtime_execution = minimum_completion_signal_pass

    if governance_ready_for_runtime_execution:
        governance_status = "governance_ready"
        top_status = "PASS"
    elif baseline_anchor.get("baseline_anchor_pass"):
        governance_status = "governance_partial"
        top_status = "PARTIAL"
    else:
        governance_status = "invalid"
        top_status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_capability_intervention_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "capability_intervention_governance_status": governance_status,
        "baseline_anchor": baseline_anchor,
        "baseline_continuity_check": continuity_check,
        "capability_intervention_lever_map": {
            "lever_map_status": lever_map_status,
            "missing_fields": lever_map_missing,
            "lever_rows": lever_map_payload,
        },
        "family_separation_rule": {
            **family_separation_payload,
            "family_separation_status": family_separation_status,
            "missing_fields": family_separation_missing,
        },
        "capability_intervention_admission": {
            **registry_summary,
            "capability_intervention_admission_rules_frozen": capability_intervention_admission_rules_frozen,
        },
        "pre_post_capability_comparison_protocol": {
            **comparison_protocol_payload,
            "comparison_protocol_ready": comparison_protocol_ready,
            "comparison_protocol_missing_fields": comparison_protocol_missing,
        },
        "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
        "minimum_completion_signal_pass": minimum_completion_signal_pass,
        "named_first_intervention_pack_ready": named_first_intervention_pack_ready,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.13.0 Governance Pack",
                "",
                f"- capability_intervention_governance_status: `{governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- named_first_intervention_pack_ready: `{named_first_intervention_pack_ready}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.13.0 capability-intervention governance pack.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v123-closeout", default=str(DEFAULT_V123_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v130_governance_pack(
        v112_closeout_path=str(args.v112_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v123_closeout_path=str(args.v123_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "capability_intervention_governance_status": payload["capability_intervention_governance_status"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
