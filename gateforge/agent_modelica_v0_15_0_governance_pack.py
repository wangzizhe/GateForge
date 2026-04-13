from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_15_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_RUNTIME_STACK_IDENTITY,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V141_CLOSEOUT_PATH,
    DEFAULT_V142_CLOSEOUT_PATH,
    DEFAULT_V143_CLOSEOUT_PATH,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V141_VERSION_DECISIONS,
    EXPECTED_V142_VERSION_DECISION,
    EXPECTED_V143_CAVEAT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_mainline_anchor": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_even_broader_change_reason": True,
    "named_reasons": [
        "governed_family_replacement_compatibility_constraint",
        "cross_layer_restructuring_runtime_safety_constraint",
        "explicit_executor_shell_replatforming_guardrail",
    ],
    "one_to_one_traceability_required": True,
    "broad_resampling_from_wider_pool_forbidden": True,
    "silent_case_replacement_forbidden": True,
}

DEFAULT_LEVER_MAP = {
    "cross_layer_execution_diagnosis_restructuring": {
        "change_family": "cross_layer_execution_diagnosis_restructuring",
        "concrete_change_surface": "coordinated_L2_L3_L4_execution_and_diagnosis_restructuring",
        "gateforge_layer": "L2_L3_L4_cross_layer",
        "relative_strength_vs_v0_14_governed_pack": "even_broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_execution_shell_replatforming": {
        "change_family": "governed_execution_shell_replatforming",
        "concrete_change_surface": "executor_shell_and_context_policy_bundle_replatforming",
        "gateforge_layer": "execution_shell_and_context_policy",
        "relative_strength_vs_v0_14_governed_pack": "even_broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_model_family_replacement_candidate": {
        "change_family": "governed_model_family_replacement_candidate",
        "concrete_change_surface": "governed_model_family_replacement_under_same_executor_contract",
        "gateforge_layer": "LLM_family_slot",
        "relative_strength_vs_v0_14_governed_pack": "even_broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
        "replacement_scope": "llm_family",
        "why_pre_post_comparison_remains_valid": (
            "The same carried 12-case baseline, executor code path, Docker/runtime stack, and comparison protocol remain fixed; "
            "the delta is isolated to the model-family slot while preserving the same executor contract."
        ),
    },
}

DEFAULT_FAMILY_SEPARATION_RULE = {
    "overlap_pairs_checked": [
        "cross_layer_execution_diagnosis_restructuring::governed_execution_shell_replatforming",
        "cross_layer_execution_diagnosis_restructuring::governed_model_family_replacement_candidate",
        "governed_execution_shell_replatforming::governed_model_family_replacement_candidate",
    ],
    "merged_family_table": [],
    "strict_separation_table": [
        {
            "family_name": "cross_layer_execution_diagnosis_restructuring",
            "distinguished_from": "governed_execution_shell_replatforming",
            "rule": "must restructure L2/L3/L4 behavior jointly rather than mainly replatform the executor shell or context-policy bundle",
        },
        {
            "family_name": "governed_model_family_replacement_candidate",
            "distinguished_from": "cross_layer_execution_diagnosis_restructuring",
            "rule": "must change the model family slot while preserving the same executor contract and carried baseline",
        },
    ],
    "family_separation_status": "ready",
}

DEFAULT_CANDIDATE_REGISTRY = {
    "candidate_rows": [
        {
            "candidate_id": "cross_layer_execution_diagnosis_restructuring_v1",
            "candidate_family": "cross_layer_execution_diagnosis_restructuring",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "single_surface_broader_change_pack_still_fails_to_shift_mainline_behavior",
            "expected_effect_type": "mainline_workflow_improvement",
            "even_broader_change_surface": "coordinated_L2_L3_L4_execution_and_diagnosis_restructuring",
            "why_broader_than_v0_14_governed_pack": "Restructures execution-policy and diagnosis-chain behavior together rather than remaining inside the governed broader-change single-pack surfaces used in v0.14.1.",
            "why_still_comparable_on_carried_baseline": "Preserves the carried 12-case baseline, same executor contract, and same Docker/runtime stack.",
            "admission_status": "rejected",
            "rejection_reason": "execution_arc_viability_not_yet_justified",
        },
        {
            "candidate_id": "governed_model_family_replacement_v1",
            "candidate_family": "governed_model_family_replacement_candidate",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "governed_broader_change_pack_does_not_reach_family_level_capability_shortfall",
            "expected_effect_type": "mainline_workflow_improvement",
            "even_broader_change_surface": "governed_model_family_replacement_under_same_executor_contract",
            "why_broader_than_v0_14_governed_pack": "Changes the capability family itself rather than only altering governed broader-change surfaces inside the same model family.",
            "why_still_comparable_on_carried_baseline": "Keeps the same carried cases, same executor code path, same Docker/runtime stack, and isolates the delta to the governed model-family slot.",
            "admission_status": "rejected",
            "rejection_reason": "execution_arc_viability_not_yet_justified",
        },
        {
            "candidate_id": "broad_unconstrained_rewrite_candidate",
            "candidate_family": "governed_model_family_replacement_candidate",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "global_underpowered_behavior",
            "expected_effect_type": "mainline_workflow_improvement",
            "even_broader_change_surface": "full_unconstrained_system_rewrite",
            "why_broader_than_v0_14_governed_pack": "Replaces multiple system surfaces without a bounded comparison contract.",
            "why_still_comparable_on_carried_baseline": "",
            "admission_status": "rejected",
            "rejection_reason": "broad_unconstrained_rewrite_out_of_scope",
        },
    ]
}

DEFAULT_COMPARISON_PROTOCOL = {
    "comparison_mode": "pre_vs_post_on_same_cases",
    "baseline_execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
    "post_change_execution_source_requirement": CURRENT_MAIN_EXECUTION_CHAIN,
    "same_case_requirement": True,
    "runtime_measurement_required": True,
    "mainline_vs_side_evidence_rule": (
        "Mainline improvement requires workflow-outcome movement on the carried same-case baseline; "
        "side-evidence-only or token-only motion cannot be upgraded into mainline material effect."
    ),
}

DEFAULT_EXECUTION_ARC_VIABILITY_OBJECT = {
    "execution_arc_viability_status": "not_justified",
    "scope_relevant_uncertainty_remains": False,
    "named_viability_question": "",
    "expected_information_gain": "marginal",
    "concrete_first_pack_available": False,
    "same_source_comparison_still_possible": True,
    "named_reason_if_not_justified": (
        "v0_14_x already exhausted governed broader-change space without material rewrite, and the remaining candidate step "
        "requires a broader-than-governed change without a non-marginal same-source execution case."
    ),
}


def _build_baseline_anchor(*, v112_closeout_path: str, v143_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    v112_builder = v112.get("product_gap_substrate_builder", {})
    v143_conclusion = load_json(v143_closeout_path).get("conclusion", {})
    substrate_table = v112_builder.get("product_gap_candidate_table") or []
    substrate_identity = v112_builder.get("carried_baseline_source", "")
    return {
        "baseline_anchor_status": "ready",
        "carried_phase_closeout_version": "v0_14_3",
        "carried_phase_caveat_label": v143_conclusion.get("explicit_caveat_label"),
        "carried_next_primary_phase_question": v143_conclusion.get("next_primary_phase_question"),
        "carried_product_gap_substrate_identity": substrate_identity,
        "carried_product_gap_substrate_size": len(substrate_table),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION
            and len(substrate_table) == EXPECTED_V112_SUBSTRATE_SIZE
            and bool(v143_conclusion.get("explicit_caveat_present"))
            and v143_conclusion.get("explicit_caveat_label") == EXPECTED_V143_CAVEAT
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
                {"row_index": idx, "task_id": row.get("task_id", ""), "missing_fields": missing_fields}
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
        for field in [
            "change_family",
            "concrete_change_surface",
            "gateforge_layer",
            "relative_strength_vs_v0_14_governed_pack",
            "in_scope_status",
        ]:
            if row.get(field) in (None, "", []):
                missing.append(f"{family_name}.{field}")
        if family_name == "governed_model_family_replacement_candidate":
            for field in ["replacement_scope", "why_pre_post_comparison_remains_valid"]:
                if row.get(field) in (None, "", []):
                    missing.append(f"{family_name}.{field}")
    return ("ready" if not missing else "partial", missing)


def _validate_family_separation(rule: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    if not rule.get("overlap_pairs_checked"):
        missing.append("overlap_pairs_checked")
    if rule.get("merged_family_table") is None:
        missing.append("merged_family_table")
    if not rule.get("strict_separation_table"):
        missing.append("strict_separation_table")
    status = rule.get("family_separation_status")
    if status not in {"ready", "partial"}:
        missing.append("family_separation_status")
    return ("ready" if not missing and status == "ready" else "partial", missing)


def _validate_candidate_registry(registry: dict, lever_map: dict) -> tuple[dict, list[dict]]:
    rows = registry.get("candidate_rows") or []
    admitted = []
    rejected = []
    missing: list[str] = []
    known_families = set(lever_map.keys())
    for row in rows:
        if not isinstance(row, dict):
            missing.append("row.object")
            continue
        for field in [
            "candidate_id",
            "candidate_family",
            "target_gap_family",
            "target_failure_mode",
            "expected_effect_type",
            "even_broader_change_surface",
            "why_broader_than_v0_14_governed_pack",
            "why_still_comparable_on_carried_baseline",
            "admission_status",
        ]:
            if row.get(field) in (None, "", []):
                if not (row.get("admission_status") == "rejected" and field == "why_still_comparable_on_carried_baseline"):
                    missing.append(f"{row.get('candidate_id', 'unknown')}.{field}")
        family = row.get("candidate_family")
        if family not in known_families:
            missing.append(f"{row.get('candidate_id', 'unknown')}.unknown_family")
        if row.get("admission_status") == "admitted":
            admitted.append(row)
        elif row.get("admission_status") == "rejected":
            rejected.append(row)
            if not row.get("rejection_reason"):
                missing.append(f"{row.get('candidate_id', 'unknown')}.rejection_reason")
    summary = {
        "even_broader_change_registry_status": "frozen" if not missing and admitted else "partial",
        "admitted_candidate_count": len(admitted),
        "rejected_candidate_count": len(rejected),
        "named_first_even_broader_change_pack_ids": [row["candidate_id"] for row in admitted],
        "admitted_rows": admitted,
        "rejected_rows": rejected,
        "rejection_reason_table": [
            {"candidate_id": row.get("candidate_id", ""), "rejection_reason": row.get("rejection_reason", "")}
            for row in rejected
        ],
        "even_broader_change_admission_rules_frozen": not missing,
        "missing_fields": missing,
    }
    return summary, admitted


def _validate_comparison_protocol(protocol: dict) -> tuple[bool, list[str]]:
    missing = []
    if protocol.get("comparison_mode") != "pre_vs_post_on_same_cases":
        missing.append("comparison_mode")
    if protocol.get("baseline_execution_source") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("baseline_execution_source")
    if protocol.get("post_change_execution_source_requirement") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("post_change_execution_source_requirement")
    if not bool(protocol.get("same_case_requirement")):
        missing.append("same_case_requirement")
    if not bool(protocol.get("runtime_measurement_required")):
        missing.append("runtime_measurement_required")
    return (not missing, missing)


def _build_viability_object(
    *,
    v141_closeout_path: str,
    v142_closeout_path: str,
    viability_object: dict | None,
    admitted_rows: list[dict],
) -> dict:
    if viability_object is not None:
        return copy.deepcopy(viability_object)

    v141 = load_json(v141_closeout_path).get("conclusion", {})
    v142 = load_json(v142_closeout_path).get("conclusion", {})
    effect_class = v141.get("broader_change_effect_class", "")
    blocker = v142.get("named_blocker_if_not_in_scope", "")
    same_source = bool(v141.get("same_execution_source"))
    same_cases = bool(v141.get("same_case_requirement_met"))
    return {
        "execution_arc_viability_status": "not_justified",
        "scope_relevant_uncertainty_remains": False,
        "named_viability_question": "",
        "expected_information_gain": "marginal",
        "concrete_first_pack_available": bool(admitted_rows) and effect_class == "side_evidence_only",
        "same_source_comparison_still_possible": same_source and same_cases,
        "named_reason_if_not_justified": blocker
        or "no_specific_non_marginal_residual_uncertainty_remains_after_v0_14_x_exhaustion",
    }


def _validate_viability_object(obj: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    status = obj.get("execution_arc_viability_status")
    if status not in {"justified", "not_justified", "invalid"}:
        missing.append("execution_arc_viability_status")
    if obj.get("expected_information_gain") not in {"marginal", "non_marginal"}:
        missing.append("expected_information_gain")
    if obj.get("scope_relevant_uncertainty_remains") not in {True, False}:
        missing.append("scope_relevant_uncertainty_remains")
    if obj.get("concrete_first_pack_available") not in {True, False}:
        missing.append("concrete_first_pack_available")
    if obj.get("same_source_comparison_still_possible") not in {True, False}:
        missing.append("same_source_comparison_still_possible")
    if status == "justified":
        for field in ["named_viability_question"]:
            if obj.get(field) in (None, "", []):
                missing.append(field)
    else:
        if not obj.get("named_reason_if_not_justified"):
            missing.append("named_reason_if_not_justified")
    if obj.get("scope_relevant_uncertainty_remains") is True and not obj.get("named_viability_question"):
        missing.append("named_viability_question")

    if status == "justified":
        justified_ok = all(
            [
                obj.get("scope_relevant_uncertainty_remains") is True,
                obj.get("expected_information_gain") == "non_marginal",
                obj.get("concrete_first_pack_available") is True,
                obj.get("same_source_comparison_still_possible") is True,
            ]
        )
        if not justified_ok:
            missing.append("justified_gate_violation")
    return ("ready" if not missing else "partial", missing)


def build_v150_governance_pack(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    v142_closeout_path: str = str(DEFAULT_V142_CLOSEOUT_PATH),
    v143_closeout_path: str = str(DEFAULT_V143_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    lever_map: dict | None = None,
    family_separation_rule: dict | None = None,
    candidate_registry: dict | None = None,
    comparison_protocol: dict | None = None,
    execution_arc_viability_object: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    baseline_anchor = _build_baseline_anchor(
        v112_closeout_path=v112_closeout_path,
        v143_closeout_path=v143_closeout_path,
    )
    continuity_check = _build_baseline_continuity_check(
        v112_closeout_path=v112_closeout_path,
        continuity_check_mode=continuity_check_mode,
    )
    lever_map_payload = copy.deepcopy(lever_map or DEFAULT_LEVER_MAP)
    family_separation_payload = copy.deepcopy(family_separation_rule or DEFAULT_FAMILY_SEPARATION_RULE)
    registry_payload = copy.deepcopy(candidate_registry or DEFAULT_CANDIDATE_REGISTRY)
    comparison_protocol_payload = copy.deepcopy(comparison_protocol or DEFAULT_COMPARISON_PROTOCOL)

    lever_map_status, lever_map_missing = _validate_lever_map(lever_map_payload)
    family_separation_status, family_separation_missing = _validate_family_separation(family_separation_payload)
    registry_summary, admitted_rows = _validate_candidate_registry(registry_payload, lever_map_payload)
    comparison_protocol_ready, comparison_protocol_missing = _validate_comparison_protocol(comparison_protocol_payload)
    viability_payload = _build_viability_object(
        v141_closeout_path=v141_closeout_path,
        v142_closeout_path=v142_closeout_path,
        viability_object=execution_arc_viability_object,
        admitted_rows=admitted_rows,
    )
    viability_status, viability_missing = _validate_viability_object(viability_payload)

    named_first_even_broader_change_pack_ready = bool(admitted_rows)
    minimum_completion_signal_pass = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["even_broader_change_registry_status"] == "frozen",
            comparison_protocol_ready,
            named_first_even_broader_change_pack_ready,
            viability_payload.get("execution_arc_viability_status") == "justified",
        ]
    )
    governance_ready_for_runtime_execution = minimum_completion_signal_pass

    governance_signals_present = any(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") in {"ready", "broken"},
            lever_map_status in {"ready", "partial"},
            family_separation_status in {"ready", "partial"},
            registry_summary["even_broader_change_registry_status"] in {"frozen", "partial"},
            comparison_protocol_ready or bool(comparison_protocol_missing),
            viability_status in {"ready", "partial"},
        ]
    )
    if minimum_completion_signal_pass:
        governance_status = "governance_ready"
        top_status = "PASS"
    elif baseline_anchor.get("baseline_anchor_pass") and governance_signals_present:
        governance_status = "governance_partial"
        top_status = "PARTIAL"
    else:
        governance_status = "invalid"
        top_status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_even_broader_change_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "even_broader_change_governance_status": governance_status,
        "even_broader_change_baseline_anchor": baseline_anchor,
        "baseline_continuity_check": continuity_check,
        "even_broader_change_lever_map": {
            "lever_map_status": lever_map_status,
            "missing_fields": lever_map_missing,
            "lever_rows": lever_map_payload,
        },
        "even_broader_change_family_separation_rule": {
            **family_separation_payload,
            "family_separation_status": family_separation_status,
            "missing_fields": family_separation_missing,
        },
        "even_broader_change_admission": registry_summary,
        "pre_post_even_broader_change_comparison_protocol": {
            **comparison_protocol_payload,
            "comparison_protocol_status": "ready" if comparison_protocol_ready else "partial",
            "comparison_protocol_missing_fields": comparison_protocol_missing,
        },
        "execution_arc_viability": {
            **viability_payload,
            "viability_object_status": viability_status,
            "missing_fields": viability_missing,
        },
        "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
        "minimum_completion_signal_pass": minimum_completion_signal_pass,
        "named_first_even_broader_change_pack_ready": named_first_even_broader_change_pack_ready,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.15.0 Even Broader Change Governance Pack",
                "",
                f"- even_broader_change_governance_status: `{governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- execution_arc_viability_status: `{viability_payload['execution_arc_viability_status']}`",
                f"- named_first_even_broader_change_pack_ready: `{named_first_even_broader_change_pack_ready}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.15.0 even-broader-change governance pack.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--v142-closeout", default=str(DEFAULT_V142_CLOSEOUT_PATH))
    parser.add_argument("--v143-closeout", default=str(DEFAULT_V143_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v150_governance_pack(
        v112_closeout_path=str(args.v112_closeout),
        v141_closeout_path=str(args.v141_closeout),
        v142_closeout_path=str(args.v142_closeout),
        v143_closeout_path=str(args.v143_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "even_broader_change_governance_status": payload["even_broader_change_governance_status"],
                "execution_arc_viability_status": payload["execution_arc_viability"]["execution_arc_viability_status"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
