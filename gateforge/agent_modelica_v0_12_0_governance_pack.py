from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_12_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_PROTOCOL_CONTRACT_VERSION,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V111_CLOSEOUT_PATH,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V117_CLOSEOUT_PATH,
    DEFERRED_REMEDY_FAMILIES,
    EXPECTED_FIRST_PASS_REMEDY_IDS,
    IN_SCOPE_REMEDY_FAMILIES,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_mainline_anchor": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_remedy_evaluation_reason": True,
    "named_reasons": [
        "remedy_specific_protocol_incompatibility",
        "instrumentation_only_substitution",
        "explicit_safety_sandboxing_requirement",
    ],
    "one_to_one_traceability_required": True,
    "broad_resampling_from_wider_pool_forbidden": True,
    "silent_case_replacement_forbidden": True,
}

DEFAULT_REMEDY_REGISTRY = {
    "allowed_remedy_families": sorted(IN_SCOPE_REMEDY_FAMILIES | DEFERRED_REMEDY_FAMILIES),
    "in_scope_remedy_families": sorted(IN_SCOPE_REMEDY_FAMILIES),
    "deferred_remedy_families": sorted(DEFERRED_REMEDY_FAMILIES),
    "remedy_rows": [
        {
            "remedy_id": "workflow_goal_reanchoring_hardening",
            "remedy_family": "context_contract_hardening",
            "target_gap_family": "context_discipline_gap",
            "target_failure_mode": "workflow_goal_drift_across_long_horizon_rounds",
            "expected_effect_type": "mainline_workflow_improvement",
            "expected_effect_scope": "reduce_surface_fix_only_and_improve_goal_alignment_on_goal_drift_sensitive_cases",
            "remedy_execution_shape": "main_execution_chain_patch",
            "bounded_change_surface": "planner_goal_reanchoring_before_each_omc_call",
            "carried_baseline_reference": "v0_11_1_patch_pack_execution.workflow_goal_reanchoring_patch_candidate",
            "admission_status": "admitted",
        },
        {
            "remedy_id": "dynamic_prompt_field_stability_hardening",
            "remedy_family": "protocol_shell_hardening",
            "target_gap_family": "protocol_robustness_gap",
            "target_failure_mode": "dynamic_prompt_field_instability_in_shell_prefix",
            "expected_effect_type": "stability_or_reliability_improvement",
            "expected_effect_scope": "improve_shell_stability_without_claiming_mainline_workflow_gain_by_default",
            "remedy_execution_shape": "instrumentation_only_patch",
            "bounded_change_surface": "dynamic_prompt_field_audit_and_prefix_stability_cleanup",
            "carried_baseline_reference": "v0_11_1_patch_pack_execution.system_prompt_dynamic_field_audit_patch_candidate",
            "admission_status": "admitted",
        },
        {
            "remedy_id": "full_omc_error_visibility_hardening",
            "remedy_family": "error_propagation_and_visibility_hardening",
            "target_gap_family": "context_discipline_gap",
            "target_failure_mode": "truncated_or_incomplete_omc_error_carryover",
            "expected_effect_type": "mainline_workflow_improvement",
            "expected_effect_scope": "improve_error_guided_adaptation_on_error_sensitive_carried_cases",
            "remedy_execution_shape": "main_execution_chain_patch",
            "bounded_change_surface": "full_omc_error_propagation_through_live_runtime_artifacts",
            "carried_baseline_reference": "v0_11_1_patch_pack_execution.full_omc_error_propagation_audit_patch_candidate",
            "admission_status": "admitted",
        },
        {
            "remedy_id": "broad_capability_rewrite_candidate",
            "remedy_family": "protocol_shell_hardening",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "broad_underpowered_core_reasoning",
            "expected_effect_type": "mainline_workflow_improvement",
            "expected_effect_scope": "unbounded_capability_jump",
            "remedy_execution_shape": "main_execution_chain_patch",
            "bounded_change_surface": "broad_prompt_or_model_replacement",
            "carried_baseline_reference": "none",
            "admission_status": "rejected",
            "rejection_reason": "disguised_broad_capability_rewrite",
        },
        {
            "remedy_id": "task_base_widening_candidate",
            "remedy_family": "efficiency_observability_only",
            "target_gap_family": "efficiency_or_latency_gap",
            "target_failure_mode": "unclear_effect_due_to_task_base_swap",
            "expected_effect_type": "observability_only",
            "expected_effect_scope": "cleaner_story_via_task_widening",
            "remedy_execution_shape": "instrumentation_only_patch",
            "bounded_change_surface": "task_pool_resampling",
            "carried_baseline_reference": "none",
            "admission_status": "rejected",
            "rejection_reason": "requires_task_base_widening",
        },
    ],
}

DEFAULT_COMPARISON_PROTOCOL = {
    "comparison_mode": "pre_vs_post_on_same_cases",
    "baseline_execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
    "post_remedy_execution_source_requirement": CURRENT_MAIN_EXECUTION_CHAIN,
    "same_case_requirement": True,
    "runtime_measurement_required": True,
    "required_docker_live_executor_posture": "docker_required_real_gateforge_runs",
    "mainline_vs_side_evidence_rule": "Mainline improvement requires workflow-outcome movement on the carried same-case baseline; sidecar-only, observability-only, or token-only movement cannot be upgraded into mainline improvement.",
    "pre_remedy_comparison_protocol_frozen": True,
}

DEFAULT_RUNTIME_REMEDY_EVALUATION_CONTRACT = {
    "required_runtime_evidence_fields": [
        "remedy_id",
        "pre_remedy_run_reference",
        "post_remedy_run_reference",
        "workflow_resolution_delta",
        "goal_alignment_delta",
        "surface_fix_only_delta",
        "unresolved_delta",
        "token_count_delta",
        "product_gap_sidecar_comparison_status",
        "effect_claim_status",
    ],
    "allowed_effect_claim_status_values": [
        "mainline_improving",
        "side_evidence_only",
        "non_material",
        "invalid",
    ],
    "runtime_remedy_evaluation_contract_frozen": True,
}


def _build_baseline_anchor(*, v112_closeout_path: str, v115_closeout_path: str, v117_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    v112_admission = v112.get("product_gap_substrate_admission", {})
    v115 = load_json(v115_closeout_path).get("conclusion", {})
    v117 = load_json(v117_closeout_path).get("conclusion", {})

    return {
        "carried_phase_question": "workflow_to_product_gap_evaluation",
        "carried_phase_version_decision": v117.get("version_decision"),
        "carried_explicit_caveat_label": v117.get("explicit_caveat_label"),
        "carried_product_gap_formal_label": v115.get("formal_adjudication_label"),
        "carried_dominant_gap_family_readout": v115.get("dominant_gap_family_readout"),
        "carried_product_gap_substrate_reference": "v0_11_2_first_product_gap_substrate_ready",
        "carried_product_gap_substrate_size": v112_admission.get("product_gap_substrate_size"),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == "v0_11_2_first_product_gap_substrate_ready"
            and v112_admission.get("product_gap_substrate_size") == 12
            and v115.get("formal_adjudication_label") == "product_gap_partial_but_interpretable"
            and bool(v115.get("execution_posture_semantics_preserved"))
            and v117.get("version_decision") == "v0_11_phase_nearly_complete_with_explicit_caveat"
            and v117.get("next_primary_phase_question") == "workflow_to_product_gap_operational_remedy_evaluation"
        ),
    }


def _validate_remedy_registry(registry: dict) -> tuple[str, list[str], list[dict], list[dict]]:
    missing: list[str] = []
    admitted_rows: list[dict] = []
    rejected_rows: list[dict] = []

    in_scope = set(registry.get("in_scope_remedy_families") or [])
    if in_scope != IN_SCOPE_REMEDY_FAMILIES:
        missing.append("in_scope_remedy_families")

    rows = registry.get("remedy_rows")
    if not isinstance(rows, list) or not rows:
        missing.append("remedy_rows")
        return "partial", missing, admitted_rows, rejected_rows

    admitted_ids = set()
    covered_families = set()
    for row in rows:
        if not isinstance(row, dict):
            missing.append("row.object")
            continue
        for field in [
            "remedy_id",
            "remedy_family",
            "target_gap_family",
            "target_failure_mode",
            "expected_effect_type",
            "expected_effect_scope",
            "remedy_execution_shape",
            "bounded_change_surface",
            "carried_baseline_reference",
            "admission_status",
        ]:
            if row.get(field) in (None, "", []):
                missing.append(f"{row.get('remedy_id', 'unknown')}.{field}")
        if row.get("admission_status") == "admitted":
            admitted_rows.append(row)
            admitted_ids.add(row.get("remedy_id"))
            covered_families.add(row.get("remedy_family"))
        elif row.get("admission_status") == "rejected":
            rejected_rows.append(row)
            if not row.get("rejection_reason"):
                missing.append(f"{row.get('remedy_id', 'unknown')}.rejection_reason")

    if admitted_ids != EXPECTED_FIRST_PASS_REMEDY_IDS:
        missing.append("first_pass_admitted_remedy_ids")
    if covered_families != IN_SCOPE_REMEDY_FAMILIES:
        missing.append("in_scope_family_coverage")
    return ("frozen" if not missing else "partial", missing, admitted_rows, rejected_rows)


def _validate_comparison_protocol(protocol: dict) -> tuple[bool, list[str]]:
    missing = []
    if protocol.get("comparison_mode") != "pre_vs_post_on_same_cases":
        missing.append("comparison_mode")
    if protocol.get("baseline_execution_source") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("baseline_execution_source")
    if protocol.get("post_remedy_execution_source_requirement") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("post_remedy_execution_source_requirement")
    if not bool(protocol.get("same_case_requirement")):
        missing.append("same_case_requirement")
    if not bool(protocol.get("runtime_measurement_required")):
        missing.append("runtime_measurement_required")
    if not bool(protocol.get("pre_remedy_comparison_protocol_frozen")):
        missing.append("pre_remedy_comparison_protocol_frozen")
    if not protocol.get("mainline_vs_side_evidence_rule"):
        missing.append("mainline_vs_side_evidence_rule")
    return (not missing, missing)


def _validate_runtime_contract(contract: dict) -> tuple[bool, list[str]]:
    missing = []
    fields = set(contract.get("required_runtime_evidence_fields") or [])
    required = {
        "remedy_id",
        "pre_remedy_run_reference",
        "post_remedy_run_reference",
        "workflow_resolution_delta",
        "goal_alignment_delta",
        "surface_fix_only_delta",
        "unresolved_delta",
        "token_count_delta",
        "product_gap_sidecar_comparison_status",
        "effect_claim_status",
    }
    if fields != required:
        missing.append("required_runtime_evidence_fields")
    allowed = set(contract.get("allowed_effect_claim_status_values") or [])
    if allowed != {"mainline_improving", "side_evidence_only", "non_material", "invalid"}:
        missing.append("allowed_effect_claim_status_values")
    if not bool(contract.get("runtime_remedy_evaluation_contract_frozen")):
        missing.append("runtime_remedy_evaluation_contract_frozen")
    return (not missing, missing)


def build_v120_governance_pack(
    *,
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v117_closeout_path: str = str(DEFAULT_V117_CLOSEOUT_PATH),
    remedy_registry: dict | None = None,
    comparison_protocol: dict | None = None,
    runtime_remedy_evaluation_contract: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    baseline_anchor = _build_baseline_anchor(
        v112_closeout_path=v112_closeout_path,
        v115_closeout_path=v115_closeout_path,
        v117_closeout_path=v117_closeout_path,
    )
    remedy_registry_payload = copy.deepcopy(remedy_registry or DEFAULT_REMEDY_REGISTRY)
    comparison_protocol_payload = copy.deepcopy(comparison_protocol or DEFAULT_COMPARISON_PROTOCOL)
    runtime_contract_payload = copy.deepcopy(runtime_remedy_evaluation_contract or DEFAULT_RUNTIME_REMEDY_EVALUATION_CONTRACT)

    remedy_registry_status, registry_missing, admitted_rows, rejected_rows = _validate_remedy_registry(remedy_registry_payload)
    comparison_protocol_frozen, comparison_missing = _validate_comparison_protocol(comparison_protocol_payload)
    runtime_contract_frozen, runtime_contract_missing = _validate_runtime_contract(runtime_contract_payload)

    remedy_admission_rules_frozen = remedy_registry_status == "frozen"
    named_first_remedy_pack_ready = {row.get("remedy_id") for row in admitted_rows} == EXPECTED_FIRST_PASS_REMEDY_IDS
    governance_ready_for_runtime_execution = (
        bool(baseline_anchor.get("baseline_anchor_pass"))
        and remedy_admission_rules_frozen
        and comparison_protocol_frozen
        and runtime_contract_frozen
        and named_first_remedy_pack_ready
    )
    minimum_completion_signal_pass = governance_ready_for_runtime_execution

    if governance_ready_for_runtime_execution:
        operational_remedy_governance_status = "governance_ready"
        top_status = "PASS"
    elif bool(baseline_anchor.get("baseline_anchor_pass")) and (
        remedy_registry_status in {"frozen", "partial"} or comparison_protocol_frozen or runtime_contract_frozen
    ):
        operational_remedy_governance_status = "governance_partial"
        top_status = "PARTIAL"
    else:
        operational_remedy_governance_status = "invalid"
        top_status = "FAIL"

    rejection_reason_table = [
        {
            "remedy_id": row.get("remedy_id"),
            "rejection_reason": row.get("rejection_reason"),
        }
        for row in rejected_rows
    ]

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "baseline_anchor": baseline_anchor,
        "remedy_registry": {
            **remedy_registry_payload,
            "remedy_registry_status": remedy_registry_status,
            "missing_fields": registry_missing,
        },
        "remedy_admission": {
            "remedy_admission_rules_frozen": remedy_admission_rules_frozen,
            "admitted_remedy_count": len(admitted_rows),
            "rejected_remedy_count": len(rejected_rows),
            "rejection_reason_table": rejection_reason_table,
        },
        "comparison_protocol": {
            **comparison_protocol_payload,
            "comparison_protocol_missing_fields": comparison_missing,
        },
        "runtime_remedy_evaluation_contract": {
            **runtime_contract_payload,
            "runtime_remedy_evaluation_contract_missing_fields": runtime_contract_missing,
        },
        "operational_remedy_governance_status": operational_remedy_governance_status,
        "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
        "minimum_completion_signal_pass": minimum_completion_signal_pass,
        "named_first_remedy_pack_ready": named_first_remedy_pack_ready,
        "in_scope_remedy_family_count": len(remedy_registry_payload["in_scope_remedy_families"]),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.12.0 Governance Pack",
                "",
                f"- operational_remedy_governance_status: `{operational_remedy_governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- named_first_remedy_pack_ready: `{named_first_remedy_pack_ready}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.12.0 operational-remedy governance pack.")
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v117-closeout", default=str(DEFAULT_V117_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v120_governance_pack(
        v111_closeout_path=str(args.v111_closeout),
        v112_closeout_path=str(args.v112_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v117_closeout_path=str(args.v117_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "operational_remedy_governance_status": payload.get("operational_remedy_governance_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
