from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_16_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_RUNTIME_STACK_IDENTITY,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V150_CLOSEOUT_PATH,
    DEFAULT_V151_CLOSEOUT_PATH,
    DEFAULT_V152_CLOSEOUT_PATH,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V151_NOT_JUSTIFIED_REASON,
    EXPECTED_V151_VERSION_DECISION,
    EXPECTED_V152_CAVEAT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_mainline_anchor": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_next_change_reason": True,
    "named_reasons": [
        "governed_evaluation_object_transition",
        "governed_baseline_rebuild_question",
        "auditable_cross_stack_replacement_question",
    ],
    "one_to_one_traceability_required": True,
    "broad_resampling_from_wider_pool_forbidden": True,
    "silent_case_replacement_forbidden": True,
}

DEFAULT_LEVER_MAP = {
    "governed_baseline_rebuild_question": {
        "change_family": "governed_baseline_rebuild_question",
        "concrete_change_surface": "rebuild_the_product_gap_substrate_as_the_explicit_evaluated_question",
        "gateforge_layer": "evaluation_baseline",
        "relative_strength_vs_v0_15": "beyond_even_broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_evaluation_object_transition": {
        "change_family": "governed_evaluation_object_transition",
        "concrete_change_surface": "transition_from_carried_product_gap_baseline_to_new_governed_evaluation_object",
        "gateforge_layer": "evaluation_object",
        "relative_strength_vs_v0_15": "beyond_even_broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_cross_stack_replacement_question": {
        "change_family": "governed_cross_stack_replacement_question",
        "concrete_change_surface": "replace_multiple_stack_layers_under_a_governed_transition_contract",
        "gateforge_layer": "cross_stack",
        "relative_strength_vs_v0_15": "beyond_even_broader",
        "in_scope_status": "deferred",
        "named_reason_if_deferred": "cross_stack_replacement_is_currently_too_broad_to_preserve_a_honest_transition_contract",
    },
}

DEFAULT_FAMILY_SEPARATION_RULE = {
    "overlap_pairs_checked": [
        "governed_baseline_rebuild_question::governed_evaluation_object_transition",
        "governed_baseline_rebuild_question::governed_cross_stack_replacement_question",
        "governed_evaluation_object_transition::governed_cross_stack_replacement_question",
    ],
    "merged_family_table": [],
    "strict_separation_table": [
        {
            "family_name": "governed_baseline_rebuild_question",
            "distinguished_from": "governed_evaluation_object_transition",
            "rule": "must ask whether the baseline itself needs governed rebuild rather than merely transitioning to a differently framed evaluation object",
        },
        {
            "family_name": "governed_evaluation_object_transition",
            "distinguished_from": "governed_cross_stack_replacement_question",
            "rule": "must remain an evaluation-object question rather than a multi-layer replacement proposal disguised as a transition",
        },
    ],
    "family_separation_status": "ready",
}

DEFAULT_CANDIDATE_REGISTRY = {
    "candidate_rows": [
        {
            "candidate_id": "governed_baseline_rebuild_v1",
            "candidate_family": "governed_baseline_rebuild_question",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "carried_v0_11_2_substrate_may_have_reached_evidence_exhaustion",
            "expected_effect_type": "evaluation_object_reframing",
            "next_change_surface": "governed_rebuild_of_the_product_gap_substrate_as_the_evaluated_question",
            "why_beyond_v0_15": "asks whether the carried baseline itself has reached exhaustion rather than proposing another still-local intervention on top of it",
            "why_still_honest_to_compare": (
                "The change is honest only as a governed baseline-rebuild question with explicit transition semantics; it is not a same-baseline pre/post intervention."
            ),
            "admission_status": "rejected",
            "rejection_reason": "no_honest_next_local_change_question_remains_on_carried_baseline",
        },
        {
            "candidate_id": "governed_evaluation_object_transition_v1",
            "candidate_family": "governed_evaluation_object_transition",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "carried_product_gap_question_may_no_longer_be_the_right_evaluation_object",
            "expected_effect_type": "evaluation_object_transition",
            "next_change_surface": "transition_to_a_new_governed_evaluation_object_under_explicit_comparison_limits",
            "why_beyond_v0_15": "asks whether the next honest move is a governed question transition rather than another local change on the carried baseline",
            "why_still_honest_to_compare": (
                "The transition would need to explain which carried signals remain interpretable and which same-baseline semantics are intentionally left behind."
            ),
            "admission_status": "rejected",
            "rejection_reason": "no_honest_next_local_change_question_remains_on_carried_baseline",
        },
    ]
}

DEFAULT_COMPARISON_PROTOCOL = {
    "protocol_mode": "evaluation_object_transition",
    "baseline_execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
    "post_change_execution_source_requirement": CURRENT_MAIN_EXECUTION_CHAIN,
    "same_case_requirement": False,
    "runtime_measurement_required": False,
    "mainline_vs_side_evidence_rule": (
        "If a later governed transition is ever admitted, it must explain explicitly which carried signals remain comparable and "
        "must not claim ordinary same-baseline pre/post meaning where the evaluation object has changed."
    ),
    "what_remains_comparable": (
        "Only the high-level interpretability of why the carried 12-case baseline was exhausted remains comparable by default."
    ),
    "what_no_longer_has_same_baseline_pre_post_meaning": (
        "A rebuilt baseline or a transitioned evaluation object does not preserve ordinary same-case delta semantics."
    ),
    "why_transition_is_still_interpretable": (
        "A transition remains interpretable only if it is frozen as the explicit evaluated question rather than silently replacing the old baseline."
    ),
}

DEFAULT_NEXT_ARC_VIABILITY_OBJECT = {
    "next_arc_viability_status": "not_justified",
    "scope_relevant_uncertainty_remains": False,
    "named_viability_question": "",
    "expected_information_gain": "marginal",
    "concrete_first_pack_available": False,
    "comparison_or_transition_still_possible": False,
    "named_reason_if_not_justified": EXPECTED_V151_NOT_JUSTIFIED_REASON,
}

DEFAULT_GOVERNANCE_OUTCOME = {
    "next_change_governance_outcome": "no_honest_next_local_change_question_remains",
    "named_governance_outcome_reason": (
        "after_v0_15_x_exhaustion_the_carried_same_12_case_baseline_no_longer_supports_a_more_local_honest_governed_question"
    ),
}


def _build_baseline_anchor(*, v112_closeout_path: str, v152_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    v112_builder = v112.get("product_gap_substrate_builder", {})
    v152_conclusion = load_json(v152_closeout_path).get("conclusion", {})
    substrate_table = v112_builder.get("product_gap_candidate_table") or []
    substrate_identity = v112_builder.get("carried_baseline_source", "")
    return {
        "baseline_anchor_status": "ready",
        "carried_phase_closeout_version": "v0_15_2",
        "carried_phase_caveat_label": v152_conclusion.get("explicit_caveat_label"),
        "carried_next_primary_phase_question": v152_conclusion.get("next_primary_phase_question"),
        "carried_product_gap_substrate_identity": substrate_identity,
        "carried_product_gap_substrate_size": len(substrate_table),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION
            and len(substrate_table) == EXPECTED_V112_SUBSTRATE_SIZE
            and bool(v152_conclusion.get("explicit_caveat_present"))
            and v152_conclusion.get("explicit_caveat_label") == EXPECTED_V152_CAVEAT
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
    continuity_breakage_count = len(named_breakage_table)
    mode_allowed = continuity_check_mode in {"schema_only", "live_dry_run", "full_live_rerun"}
    status = "ready" if mode_allowed and len(rows) == EXPECTED_V112_SUBSTRATE_SIZE and continuity_breakage_count == 0 else "broken"
    return {
        "baseline_continuity_check_status": status,
        "continuity_check_mode": continuity_check_mode,
        "continuity_runtime_stack_identity": CURRENT_RUNTIME_STACK_IDENTITY,
        "carried_case_count": len(rows),
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
            "relative_strength_vs_v0_15",
            "in_scope_status",
        ]:
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


def _validate_candidate_registry(registry: dict, lever_map: dict) -> tuple[dict, list[dict], list[dict]]:
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
            "next_change_surface",
            "why_beyond_v0_15",
            "why_still_honest_to_compare",
            "admission_status",
        ]:
            if row.get(field) in (None, "", []):
                if not (row.get("admission_status") == "rejected" and field == "why_still_honest_to_compare"):
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
        "next_change_registry_status": "frozen" if not missing else "partial",
        "admitted_candidate_count": len(admitted),
        "rejected_candidate_count": len(rejected),
        "named_first_next_change_pack_ids": [row["candidate_id"] for row in admitted],
        "admitted_rows": admitted,
        "rejected_rows": rejected,
        "rejection_reason_table": [
            {"candidate_id": row.get("candidate_id", ""), "rejection_reason": row.get("rejection_reason", "")}
            for row in rejected
        ],
        "next_change_admission_rules_frozen": not missing,
        "missing_fields": missing,
    }
    return summary, admitted, rejected


def _validate_protocol(protocol: dict) -> tuple[str, list[str]]:
    missing = []
    mode = protocol.get("protocol_mode")
    if mode not in {"same_baseline_pre_post", "evaluation_object_transition"}:
        missing.append("protocol_mode")
    if protocol.get("baseline_execution_source") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("baseline_execution_source")
    if protocol.get("post_change_execution_source_requirement") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("post_change_execution_source_requirement")
    if protocol.get("runtime_measurement_required") not in {True, False}:
        missing.append("runtime_measurement_required")
    if mode == "evaluation_object_transition":
        for field in [
            "what_remains_comparable",
            "what_no_longer_has_same_baseline_pre_post_meaning",
            "why_transition_is_still_interpretable",
        ]:
            if protocol.get(field) in (None, "", []):
                missing.append(field)
    else:
        if protocol.get("same_case_requirement") is not True:
            missing.append("same_case_requirement")
    return ("ready" if not missing else "partial", missing)


def _build_viability_object(
    *,
    v150_closeout_path: str,
    v151_closeout_path: str,
    viability_object: dict | None,
    admitted_rows: list[dict],
) -> dict:
    if viability_object is not None:
        return copy.deepcopy(viability_object)

    v150 = load_json(v150_closeout_path).get("conclusion", {})
    v151 = load_json(v151_closeout_path).get("conclusion", {})
    reason = v151.get("named_reason_if_not_justified") or EXPECTED_V151_NOT_JUSTIFIED_REASON
    return {
        "next_arc_viability_status": "not_justified",
        "scope_relevant_uncertainty_remains": False,
        "named_viability_question": "",
        "expected_information_gain": "marginal",
        "concrete_first_pack_available": bool(admitted_rows) and v150.get("governance_ready_for_runtime_execution") is True,
        "comparison_or_transition_still_possible": False,
        "named_reason_if_not_justified": reason,
    }


def _validate_viability_object(obj: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    status = obj.get("next_arc_viability_status")
    if status not in {"justified", "not_justified", "invalid"}:
        missing.append("next_arc_viability_status")
    if obj.get("expected_information_gain") not in {"marginal", "non_marginal"}:
        missing.append("expected_information_gain")
    if obj.get("scope_relevant_uncertainty_remains") not in {True, False}:
        missing.append("scope_relevant_uncertainty_remains")
    if obj.get("concrete_first_pack_available") not in {True, False}:
        missing.append("concrete_first_pack_available")
    if obj.get("comparison_or_transition_still_possible") not in {True, False}:
        missing.append("comparison_or_transition_still_possible")
    if status == "justified":
        if obj.get("named_viability_question") in (None, "", []):
            missing.append("named_viability_question")
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
                obj.get("comparison_or_transition_still_possible") is True,
            ]
        )
        if not justified_ok:
            missing.append("justified_gate_violation")
    return ("ready" if not missing else "partial", missing)


def _build_governance_outcome(governance_outcome: dict | None) -> dict:
    if governance_outcome is not None:
        return copy.deepcopy(governance_outcome)
    return copy.deepcopy(DEFAULT_GOVERNANCE_OUTCOME)


def _validate_governance_outcome(obj: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    outcome = obj.get("next_change_governance_outcome")
    if outcome not in {
        "next_honest_governed_question_exists",
        "no_honest_next_local_change_question_remains",
        "invalid",
    }:
        missing.append("next_change_governance_outcome")
    if not obj.get("named_governance_outcome_reason"):
        missing.append("named_governance_outcome_reason")
    return ("ready" if not missing else "partial", missing)


def build_v160_governance_pack(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v150_closeout_path: str = str(DEFAULT_V150_CLOSEOUT_PATH),
    v151_closeout_path: str = str(DEFAULT_V151_CLOSEOUT_PATH),
    v152_closeout_path: str = str(DEFAULT_V152_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    lever_map: dict | None = None,
    family_separation_rule: dict | None = None,
    candidate_registry: dict | None = None,
    comparison_or_transition_protocol: dict | None = None,
    next_arc_viability_object: dict | None = None,
    governance_outcome: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    baseline_anchor = _build_baseline_anchor(
        v112_closeout_path=v112_closeout_path,
        v152_closeout_path=v152_closeout_path,
    )
    continuity_check = _build_baseline_continuity_check(
        v112_closeout_path=v112_closeout_path,
        continuity_check_mode=continuity_check_mode,
    )
    lever_map_payload = copy.deepcopy(lever_map or DEFAULT_LEVER_MAP)
    family_separation_payload = copy.deepcopy(family_separation_rule or DEFAULT_FAMILY_SEPARATION_RULE)
    registry_payload = copy.deepcopy(candidate_registry or DEFAULT_CANDIDATE_REGISTRY)
    protocol_payload = copy.deepcopy(comparison_or_transition_protocol or DEFAULT_COMPARISON_PROTOCOL)
    lever_map_status, lever_map_missing = _validate_lever_map(lever_map_payload)
    family_separation_status, family_separation_missing = _validate_family_separation(family_separation_payload)
    registry_summary, admitted_rows, _rejected_rows = _validate_candidate_registry(registry_payload, lever_map_payload)
    protocol_status, protocol_missing = _validate_protocol(protocol_payload)
    viability_payload = _build_viability_object(
        v150_closeout_path=v150_closeout_path,
        v151_closeout_path=v151_closeout_path,
        viability_object=next_arc_viability_object,
        admitted_rows=admitted_rows,
    )
    viability_object_status, viability_missing = _validate_viability_object(viability_payload)
    governance_outcome_payload = _build_governance_outcome(governance_outcome)
    governance_outcome_status, governance_outcome_missing = _validate_governance_outcome(governance_outcome_payload)

    named_first_next_change_pack_ready = bool(admitted_rows)
    minimum_completion_signal_pass = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["next_change_registry_status"] == "frozen",
            protocol_status == "ready",
            named_first_next_change_pack_ready,
            viability_payload.get("next_arc_viability_status") == "justified",
            governance_outcome_payload.get("next_change_governance_outcome") == "next_honest_governed_question_exists",
        ]
    )
    governance_structure_ready = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["next_change_registry_status"] == "frozen",
            protocol_status == "ready",
            governance_outcome_status == "ready",
        ]
    )
    governance_ready_for_runtime_execution = minimum_completion_signal_pass

    if minimum_completion_signal_pass:
        governance_status = "governance_ready"
        top_status = "PASS"
    elif governance_structure_ready and governance_outcome_payload.get("next_change_governance_outcome") == "no_honest_next_local_change_question_remains":
        governance_status = "governance_ready"
        top_status = "PASS"
    elif baseline_anchor.get("baseline_anchor_pass"):
        governance_status = "governance_partial"
        top_status = "PARTIAL"
    else:
        governance_status = "invalid"
        top_status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_next_change_question_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "next_change_question_governance_status": governance_status,
        "next_change_baseline_anchor": baseline_anchor,
        "baseline_continuity_check": continuity_check,
        "next_change_lever_map": {
            "lever_map_status": lever_map_status,
            "missing_fields": lever_map_missing,
            "lever_rows": lever_map_payload,
        },
        "next_change_family_separation_rule": {
            **family_separation_payload,
            "family_separation_status": family_separation_status,
            "missing_fields": family_separation_missing,
        },
        "next_change_admission": registry_summary,
        "comparison_or_transition_protocol": {
            **protocol_payload,
            "comparison_or_transition_protocol_status": protocol_status,
            "protocol_missing_fields": protocol_missing,
        },
        "next_arc_viability": {
            **viability_payload,
            "viability_object_status": viability_object_status,
            "missing_fields": viability_missing,
        },
        "governance_outcome": {
            **governance_outcome_payload,
            "governance_outcome_status": governance_outcome_status,
            "missing_fields": governance_outcome_missing,
        },
        "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
        "minimum_completion_signal_pass": minimum_completion_signal_pass,
        "named_first_next_change_pack_ready": named_first_next_change_pack_ready,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.16.0 Next Change Question Governance Pack",
                "",
                f"- next_change_question_governance_status: `{governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- next_arc_viability_status: `{viability_payload['next_arc_viability_status']}`",
                f"- next_change_governance_outcome: `{governance_outcome_payload['next_change_governance_outcome']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.16.0 next-change-question governance pack.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v150-closeout", default=str(DEFAULT_V150_CLOSEOUT_PATH))
    parser.add_argument("--v151-closeout", default=str(DEFAULT_V151_CLOSEOUT_PATH))
    parser.add_argument("--v152-closeout", default=str(DEFAULT_V152_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v160_governance_pack(
        v112_closeout_path=str(args.v112_closeout),
        v150_closeout_path=str(args.v150_closeout),
        v151_closeout_path=str(args.v151_closeout),
        v152_closeout_path=str(args.v152_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "next_change_question_governance_status": payload["next_change_question_governance_status"],
                "next_arc_viability_status": payload["next_arc_viability"]["next_arc_viability_status"],
                "next_change_governance_outcome": payload["governance_outcome"]["next_change_governance_outcome"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
