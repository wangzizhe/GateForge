from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_17_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_RUNTIME_STACK_IDENTITY,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V160_CLOSEOUT_PATH,
    DEFAULT_V161_CLOSEOUT_PATH,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V160_GOVERNANCE_OUTCOME,
    EXPECTED_V160_VERSION_DECISION,
    EXPECTED_V161_CAVEAT,
    EXPECTED_V161_NEXT_PRIMARY_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_reference_object": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_transition_reason": True,
    "named_reasons": [
        "governed_baseline_rebuild_question",
        "governed_evaluation_object_transition",
        "governed_evidence_object_transition",
    ],
    "one_to_one_traceability_required": True,
    "silent_case_replacement_forbidden": True,
    "broad_resampling_from_wider_pool_forbidden": True,
}

DEFAULT_LEVER_MAP = {
    "governed_baseline_rebuild_question": {
        "transition_family": "governed_baseline_rebuild_question",
        "concrete_change_surface": "rebuild_the_carried_product_gap_substrate_as_the_explicit_transition_question",
        "gateforge_layer": "evaluation_baseline",
        "relative_strength_vs_v0_16": "beyond_local_question_exhaustion",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_evaluation_object_transition": {
        "transition_family": "governed_evaluation_object_transition",
        "concrete_change_surface": "transition_what_the_project_is_explicitly_evaluating_after_carried_baseline_exhaustion",
        "gateforge_layer": "evaluation_object",
        "relative_strength_vs_v0_16": "beyond_local_question_exhaustion",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_evidence_object_transition": {
        "transition_family": "governed_evidence_object_transition",
        "concrete_change_surface": "transition_which_evidence_object_is_primary_without_silent_narrative_reset",
        "gateforge_layer": "evidence_object",
        "relative_strength_vs_v0_16": "beyond_local_question_exhaustion",
        "in_scope_status": "deferred",
        "named_reason_if_deferred": (
            "deferred_until_family_separation_confirms_it_is_distinct_from_evaluation_object_transition"
        ),
    },
}

DEFAULT_FAMILY_SEPARATION_RULE = {
    "overlap_pairs_checked": [
        "governed_baseline_rebuild_question::governed_evaluation_object_transition",
        "governed_baseline_rebuild_question::governed_evidence_object_transition",
        "governed_evaluation_object_transition::governed_evidence_object_transition",
    ],
    "merged_family_table": [],
    "strict_separation_table": [
        {
            "family_name": "governed_baseline_rebuild_question",
            "distinguished_from": "governed_evaluation_object_transition",
            "rule": "must ask whether the carried substrate itself has reached exhaustion rather than merely reframing the evaluation question",
        },
        {
            "family_name": "governed_evaluation_object_transition",
            "distinguished_from": "governed_evidence_object_transition",
            "rule": "must change what the project is evaluating, not only which evidence object is treated as primary",
        },
    ],
    "family_separation_status": "ready",
}

DEFAULT_CANDIDATE_REGISTRY = {
    "candidate_rows": [
        {
            "candidate_id": "governed_baseline_rebuild_v2",
            "candidate_family": "governed_baseline_rebuild_question",
            "transition_target": "rebuild_the_carried_product_gap_substrate_under_an_explicit_transition_contract",
            "target_gap_family": "residual_core_capability_gap",
            "expected_effect_type": "baseline_rebuild_question",
            "what_remains_comparable": "the high-level reading that the carried 12-case baseline reached honest local-question exhaustion",
            "what_no_longer_has_same_baseline_meaning": "ordinary same-case pre_post_delta semantics on the original carried substrate",
            "why_transition_is_interpretable": "the rebuild is framed as the explicit evaluated question rather than as a silent reset",
            "why_non_marginal_information_gain_still_exists": "",
            "admission_status": "rejected",
            "rejection_reason": "no_honest_transition_question_remains_after_carried_evidence_exhaustion_readout",
        },
        {
            "candidate_id": "governed_evaluation_object_transition_v2",
            "candidate_family": "governed_evaluation_object_transition",
            "transition_target": "move_from_the_carried_product_gap_question_to_a_new_governed_evaluation_object",
            "target_gap_family": "residual_core_capability_gap",
            "expected_effect_type": "evaluation_object_transition",
            "what_remains_comparable": "the reason the carried baseline exhausted its honest local-question budget",
            "what_no_longer_has_same_baseline_meaning": "direct same-baseline pre_post comparisons against the original product-gap question",
            "why_transition_is_interpretable": "the new evaluation object would be named explicitly with auditable loss-of-comparability semantics",
            "why_non_marginal_information_gain_still_exists": "",
            "admission_status": "rejected",
            "rejection_reason": "no_honest_transition_question_remains_after_carried_evidence_exhaustion_readout",
        },
        {
            "candidate_id": "governed_evidence_object_transition_v1",
            "candidate_family": "governed_evidence_object_transition",
            "transition_target": "change_which_evidence_object_is_primary_while_preserving_a_governed_transition_contract",
            "target_gap_family": "residual_core_capability_gap",
            "expected_effect_type": "evidence_object_transition",
            "what_remains_comparable": "the carried explanation that the original evidence object has reached honest local-question exhaustion",
            "what_no_longer_has_same_baseline_meaning": "same-evidence-object interpretability claims on the original carried substrate",
            "why_transition_is_interpretable": "the transition would need to state exactly which evidence objects changed and why that is still auditable",
            "why_non_marginal_information_gain_still_exists": "",
            "admission_status": "rejected",
            "rejection_reason": "deferred_until_family_separation_confirms_distinctness_and_no_honest_transition_question_remains_by_default",
        },
    ]
}

DEFAULT_TRANSITION_PROTOCOL = {
    "protocol_mode": "evidence_object_transition",
    "baseline_execution_source": CURRENT_MAIN_EXECUTION_CHAIN,
    "post_transition_execution_source_requirement": CURRENT_MAIN_EXECUTION_CHAIN,
    "same_case_requirement": False,
    "runtime_measurement_required": False,
    "comparability_loss_rule": (
        "Any future transition must explicitly name what remains comparable, what no longer has ordinary same-baseline meaning, "
        "and why the transition remains interpretable rather than silently replacing the baseline."
    ),
    "what_remains_comparable": "the carried explanation for why the same 12-case baseline no longer supports honest local next-change questions",
    "what_no_longer_has_same_baseline_pre_post_meaning": (
        "baseline rebuild and evaluation or evidence-object transition questions do not preserve ordinary same-case delta semantics"
    ),
    "why_transition_is_still_interpretable": (
        "A transition remains interpretable only if it is frozen as the explicit evaluated transition question with named comparability loss."
    ),
}

DEFAULT_TRANSITION_ARC_VIABILITY_OBJECT = {
    "transition_arc_viability_status": "not_justified",
    "scope_relevant_uncertainty_remains": False,
    "named_viability_question": "",
    "expected_information_gain": "marginal",
    "concrete_first_pack_available": False,
    "transition_still_possible": False,
    "named_reason_if_not_justified": (
        "carried_evidence_exhaustion_readout_does_not_leave_a_more_honest_transition_question_on_the_same_governed_frontier"
    ),
}

DEFAULT_GOVERNANCE_OUTCOME = {
    "transition_governance_outcome": "no_honest_transition_question_remains",
    "named_governance_outcome_reason": (
        "after_the_carried_v0_16_x_exhaustion_readout_no_governed_transition_question_survives_with_non_marginal_information_gain"
    ),
}


def _build_baseline_anchor(*, v112_closeout_path: str, v161_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    builder = v112.get("product_gap_substrate_builder", {})
    v161_conclusion = load_json(v161_closeout_path).get("conclusion", {})
    rows = builder.get("product_gap_candidate_table") or []
    identity = builder.get("carried_baseline_source", "")
    return {
        "baseline_anchor_status": "ready",
        "carried_phase_closeout_version": "v0_16_1",
        "carried_phase_caveat_label": v161_conclusion.get("explicit_caveat_label", ""),
        "carried_next_primary_phase_question": v161_conclusion.get("next_primary_phase_question", ""),
        "carried_product_gap_substrate_identity": identity,
        "carried_product_gap_substrate_size": len(rows),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION
            and len(rows) == EXPECTED_V112_SUBSTRATE_SIZE
            and v161_conclusion.get("explicit_caveat_label") == EXPECTED_V161_CAVEAT
            and v161_conclusion.get("next_primary_phase_question") == EXPECTED_V161_NEXT_PRIMARY_QUESTION
        ),
    }


def _build_carried_evidence_exhaustion_readout(*, v160_closeout_path: str, v161_closeout_path: str) -> dict:
    v160_conclusion = load_json(v160_closeout_path).get("conclusion", {})
    v161_conclusion = load_json(v161_closeout_path).get("conclusion", {})
    exhaustion_confirmed = (
        v160_conclusion.get("version_decision") == EXPECTED_V160_VERSION_DECISION
        and v160_conclusion.get("next_change_governance_outcome") == EXPECTED_V160_GOVERNANCE_OUTCOME
        and v161_conclusion.get("explicit_caveat_label") == EXPECTED_V161_CAVEAT
    )
    return {
        "carried_evidence_exhaustion_readout_status": "ready" if exhaustion_confirmed else "partial",
        "carried_local_question_exhaustion_confirmed": exhaustion_confirmed,
        "named_exhaustion_reason": (
            "the_carried_same_12_case_baseline_has_already_answered_the_last_honest_local_next_change_question"
            if exhaustion_confirmed
            else ""
        ),
        "carried_closeout_reference": "v0_16_1_closeout",
        "what_the_carried_baseline_has_already_answered": (
            "it has already answered that no further honest local next-change question remains on the same carried 12-case baseline"
        ),
        "what_the_carried_baseline_no_longer_honestly_supports": (
            "another same-class local change or intervention loop presented as if it were still a new honest question"
        ),
    }


def _build_baseline_continuity_check(*, v112_closeout_path: str, continuity_check_mode: str) -> dict:
    v112 = load_json(v112_closeout_path)
    rows = (v112.get("product_gap_substrate_builder") or {}).get("product_gap_candidate_table") or []
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
    mode_allowed = continuity_check_mode in {"schema_only", "live_dry_run", "full_live_rerun"}
    continuity_breakage_count = len(named_breakage_table)
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
            "transition_family",
            "concrete_change_surface",
            "gateforge_layer",
            "relative_strength_vs_v0_16",
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
    admitted: list[dict] = []
    rejected: list[dict] = []
    missing: list[str] = []
    known_families = set(lever_map.keys())
    for row in rows:
        if not isinstance(row, dict):
            missing.append("row.object")
            continue
        for field in [
            "candidate_id",
            "candidate_family",
            "transition_target",
            "target_gap_family",
            "expected_effect_type",
            "what_remains_comparable",
            "what_no_longer_has_same_baseline_meaning",
            "why_transition_is_interpretable",
            "admission_status",
        ]:
            if row.get(field) in (None, "", []):
                if not (row.get("admission_status") == "rejected" and field == "why_transition_is_interpretable"):
                    missing.append(f"{row.get('candidate_id', 'unknown')}.{field}")
        if row.get("candidate_family") not in known_families:
            missing.append(f"{row.get('candidate_id', 'unknown')}.unknown_family")
        if row.get("candidate_id") == "carried_evidence_exhaustion_readout":
            missing.append("candidate_registry.must_not_include_carried_evidence_exhaustion_readout")
        if row.get("admission_status") == "admitted":
            admitted.append(row)
            if not row.get("why_non_marginal_information_gain_still_exists"):
                missing.append(f"{row.get('candidate_id', 'unknown')}.why_non_marginal_information_gain_still_exists")
        elif row.get("admission_status") == "rejected":
            rejected.append(row)
            if not row.get("rejection_reason"):
                missing.append(f"{row.get('candidate_id', 'unknown')}.rejection_reason")
    summary = {
        "transition_registry_status": "frozen" if not missing else "partial",
        "admitted_candidate_count": len(admitted),
        "rejected_candidate_count": len(rejected),
        "named_first_transition_pack_ids": [row["candidate_id"] for row in admitted],
        "admitted_rows": admitted,
        "rejected_rows": rejected,
        "rejection_reason_table": [
            {"candidate_id": row.get("candidate_id", ""), "rejection_reason": row.get("rejection_reason", "")}
            for row in rejected
        ],
        "transition_admission_rules_frozen": not missing,
        "missing_fields": missing,
    }
    return summary, admitted, rejected


def _validate_protocol(protocol: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    mode = protocol.get("protocol_mode")
    if mode not in {"same_baseline_pre_post", "baseline_transition", "evaluation_object_transition", "evidence_object_transition"}:
        missing.append("protocol_mode")
    if protocol.get("baseline_execution_source") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("baseline_execution_source")
    if protocol.get("post_transition_execution_source_requirement") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("post_transition_execution_source_requirement")
    if protocol.get("runtime_measurement_required") not in {True, False}:
        missing.append("runtime_measurement_required")
    if mode == "same_baseline_pre_post":
        if protocol.get("same_case_requirement") is not True:
            missing.append("same_case_requirement")
    else:
        for field in [
            "comparability_loss_rule",
            "what_remains_comparable",
            "what_no_longer_has_same_baseline_pre_post_meaning",
            "why_transition_is_still_interpretable",
        ]:
            if protocol.get(field) in (None, "", []):
                missing.append(field)
    return ("ready" if not missing else "partial", missing)


def _build_viability_object(viability_object: dict | None, admitted_rows: list[dict]) -> dict:
    if viability_object is not None:
        return copy.deepcopy(viability_object)
    return {
        **copy.deepcopy(DEFAULT_TRANSITION_ARC_VIABILITY_OBJECT),
        "concrete_first_pack_available": bool(admitted_rows),
    }


def _validate_viability_object(obj: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    status = obj.get("transition_arc_viability_status")
    if status not in {"justified", "not_justified", "invalid"}:
        missing.append("transition_arc_viability_status")
    if obj.get("expected_information_gain") not in {"marginal", "non_marginal"}:
        missing.append("expected_information_gain")
    if obj.get("scope_relevant_uncertainty_remains") not in {True, False}:
        missing.append("scope_relevant_uncertainty_remains")
    if obj.get("concrete_first_pack_available") not in {True, False}:
        missing.append("concrete_first_pack_available")
    if obj.get("transition_still_possible") not in {True, False}:
        missing.append("transition_still_possible")
    if status == "justified":
        if obj.get("named_viability_question") in (None, "", []):
            missing.append("named_viability_question")
        justified_ok = all(
            [
                obj.get("scope_relevant_uncertainty_remains") is True,
                obj.get("expected_information_gain") == "non_marginal",
                obj.get("concrete_first_pack_available") is True,
                obj.get("transition_still_possible") is True,
            ]
        )
        if not justified_ok:
            missing.append("justified_gate_violation")
    else:
        if not obj.get("named_reason_if_not_justified"):
            missing.append("named_reason_if_not_justified")
    if obj.get("scope_relevant_uncertainty_remains") is True and not obj.get("named_viability_question"):
        missing.append("named_viability_question")
    return ("ready" if not missing else "partial", missing)


def _build_governance_outcome(governance_outcome: dict | None) -> dict:
    if governance_outcome is not None:
        return copy.deepcopy(governance_outcome)
    return copy.deepcopy(DEFAULT_GOVERNANCE_OUTCOME)


def _validate_governance_outcome(obj: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    outcome = obj.get("transition_governance_outcome")
    if outcome not in {"next_honest_transition_question_exists", "no_honest_transition_question_remains", "invalid"}:
        missing.append("transition_governance_outcome")
    if not obj.get("named_governance_outcome_reason"):
        missing.append("named_governance_outcome_reason")
    return ("ready" if not missing else "partial", missing)


def build_v170_governance_pack(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v160_closeout_path: str = str(DEFAULT_V160_CLOSEOUT_PATH),
    v161_closeout_path: str = str(DEFAULT_V161_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    lever_map: dict | None = None,
    family_separation_rule: dict | None = None,
    candidate_registry: dict | None = None,
    transition_protocol: dict | None = None,
    transition_arc_viability_object: dict | None = None,
    governance_outcome: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    baseline_anchor = _build_baseline_anchor(v112_closeout_path=v112_closeout_path, v161_closeout_path=v161_closeout_path)
    exhaustion_readout = _build_carried_evidence_exhaustion_readout(
        v160_closeout_path=v160_closeout_path,
        v161_closeout_path=v161_closeout_path,
    )
    continuity_check = _build_baseline_continuity_check(
        v112_closeout_path=v112_closeout_path,
        continuity_check_mode=continuity_check_mode,
    )
    lever_map_payload = copy.deepcopy(lever_map or DEFAULT_LEVER_MAP)
    family_separation_payload = copy.deepcopy(family_separation_rule or DEFAULT_FAMILY_SEPARATION_RULE)
    registry_payload = copy.deepcopy(candidate_registry or DEFAULT_CANDIDATE_REGISTRY)
    protocol_payload = copy.deepcopy(transition_protocol or DEFAULT_TRANSITION_PROTOCOL)
    lever_map_status, lever_map_missing = _validate_lever_map(lever_map_payload)
    family_separation_status, family_separation_missing = _validate_family_separation(family_separation_payload)
    registry_summary, admitted_rows, _rejected_rows = _validate_candidate_registry(registry_payload, lever_map_payload)
    protocol_status, protocol_missing = _validate_protocol(protocol_payload)
    viability_payload = _build_viability_object(transition_arc_viability_object, admitted_rows)
    viability_object_status, viability_missing = _validate_viability_object(viability_payload)
    governance_outcome_payload = _build_governance_outcome(governance_outcome)
    governance_outcome_status, governance_outcome_missing = _validate_governance_outcome(governance_outcome_payload)

    named_first_transition_pack_ready = bool(admitted_rows)
    minimum_completion_signal_pass = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            exhaustion_readout.get("carried_evidence_exhaustion_readout_status") == "ready",
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["transition_registry_status"] == "frozen",
            protocol_status == "ready",
            named_first_transition_pack_ready,
            viability_payload.get("transition_arc_viability_status") == "justified",
            governance_outcome_payload.get("transition_governance_outcome") == "next_honest_transition_question_exists",
        ]
    )
    governance_structure_ready = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            exhaustion_readout.get("carried_evidence_exhaustion_readout_status") == "ready",
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["transition_registry_status"] == "frozen",
            protocol_status == "ready",
            governance_outcome_status == "ready",
        ]
    )
    governance_ready_for_runtime_execution = minimum_completion_signal_pass

    if minimum_completion_signal_pass:
        governance_status = "governance_ready"
        top_status = "PASS"
    elif governance_structure_ready and governance_outcome_payload.get("transition_governance_outcome") == "no_honest_transition_question_remains":
        governance_status = "governance_ready"
        top_status = "PASS"
    elif baseline_anchor.get("baseline_anchor_pass"):
        governance_status = "governance_partial"
        top_status = "PARTIAL"
    else:
        governance_status = "invalid"
        top_status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_transition_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "transition_governance_status": governance_status,
        "transition_baseline_anchor": baseline_anchor,
        "carried_evidence_exhaustion_readout": exhaustion_readout,
        "baseline_continuity_check": continuity_check,
        "transition_lever_map": {
            "lever_map_status": lever_map_status,
            "lever_rows": lever_map_payload,
            "missing_fields": lever_map_missing,
        },
        "transition_family_separation_rule": {
            **family_separation_payload,
            "family_separation_status": family_separation_status,
            "missing_fields": family_separation_missing,
        },
        "transition_admission": registry_summary,
        "transition_protocol": {
            **protocol_payload,
            "transition_protocol_status": protocol_status,
            "protocol_missing_fields": protocol_missing,
        },
        "transition_arc_viability": {
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
        "named_first_transition_pack_ready": named_first_transition_pack_ready,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.17.0 Transition Governance Pack",
                "",
                f"- transition_governance_status: `{governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- transition_arc_viability_status: `{viability_payload['transition_arc_viability_status']}`",
                f"- transition_governance_outcome: `{governance_outcome_payload['transition_governance_outcome']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.17.0 transition governance pack.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v160-closeout", default=str(DEFAULT_V160_CLOSEOUT_PATH))
    parser.add_argument("--v161-closeout", default=str(DEFAULT_V161_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v170_governance_pack(
        v112_closeout_path=str(args.v112_closeout),
        v160_closeout_path=str(args.v160_closeout),
        v161_closeout_path=str(args.v161_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "transition_governance_status": payload["transition_governance_status"],
                "transition_arc_viability_status": payload["transition_arc_viability"]["transition_arc_viability_status"],
                "transition_governance_outcome": payload["governance_outcome"]["transition_governance_outcome"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
