from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_18_0_common import (
    CURRENT_RUNTIME_STACK_IDENTITY,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V161_CLOSEOUT_PATH,
    DEFAULT_V170_CLOSEOUT_PATH,
    DEFAULT_V171_CLOSEOUT_PATH,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V161_CAVEAT,
    EXPECTED_V161_VERSION_DECISION,
    EXPECTED_V170_GOVERNANCE_OUTCOME,
    EXPECTED_V170_VERSION_DECISION,
    EXPECTED_V171_CAVEAT,
    EXPECTED_V171_NEXT_PRIMARY_QUESTION,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_reference_object": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_next_move_reason": True,
    "named_reasons": [
        "governed_evidence_boundary_conclusion_question",
        "governed_methodological_reframing_question",
        "governed_baseline_reset_with_loss_accounting",
    ],
    "one_to_one_traceability_required": True,
    "silent_case_replacement_forbidden": True,
    "broad_resampling_from_wider_pool_forbidden": True,
}

DEFAULT_LEVER_MAP = {
    "governed_evidence_boundary_conclusion_question": {
        "candidate_family": "governed_evidence_boundary_conclusion_question",
        "concrete_change_surface": "freeze_the_carried_evidence_boundary_itself_as_the_evaluated_result",
        "gateforge_layer": "evidence_boundary",
        "relative_strength_vs_v0_17": "beyond_transition_question_exhaustion",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_methodological_reframing_question": {
        "candidate_family": "governed_methodological_reframing_question",
        "concrete_change_surface": "reframe_what_the_project_is_honestly_trying_to_conclude_from_the_carried_evidence",
        "gateforge_layer": "methodology",
        "relative_strength_vs_v0_17": "beyond_transition_question_exhaustion",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_baseline_reset_with_loss_accounting": {
        "candidate_family": "governed_baseline_reset_with_loss_accounting",
        "concrete_change_surface": "reset_the_baseline_only_under_explicit_named_loss_of_comparability",
        "gateforge_layer": "evaluation_baseline",
        "relative_strength_vs_v0_17": "beyond_transition_question_exhaustion",
        "in_scope_status": "deferred",
        "named_reason_if_deferred": "deferred_until_it_proves_it_is_not_just_a_disguised_restart",
    },
}

DEFAULT_FAMILY_SEPARATION_RULE = {
    "overlap_pairs_checked": [
        "governed_evidence_boundary_conclusion_question::governed_methodological_reframing_question",
        "governed_evidence_boundary_conclusion_question::governed_baseline_reset_with_loss_accounting",
        "governed_methodological_reframing_question::governed_baseline_reset_with_loss_accounting",
    ],
    "merged_family_table": [],
    "strict_separation_table": [
        {
            "family_name": "governed_evidence_boundary_conclusion_question",
            "distinguished_from": "governed_methodological_reframing_question",
            "rule": "must conclude that the carried evidence itself has said enough rather than reframing the project question",
        },
        {
            "family_name": "governed_methodological_reframing_question",
            "distinguished_from": "governed_baseline_reset_with_loss_accounting",
            "rule": "must change the framing of what the project concludes, not silently reset the baseline under restart rhetoric",
        },
    ],
    "family_separation_status": "ready",
}

DEFAULT_CANDIDATE_REGISTRY = {
    "candidate_rows": [
        {
            "candidate_id": "governed_evidence_boundary_conclusion_v1",
            "candidate_family": "governed_evidence_boundary_conclusion_question",
            "reframing_target": "freeze_the_carried_evidence_boundary_as_the_primary_result",
            "why_this_is_not_a_silent_restart": "it does not replace the baseline or evaluation object; it formalizes the limit of what the carried evidence can honestly support",
            "what_remains_interpretable": "the multi-phase carried chain showing repeated exhaustion of local and transition-question routes",
            "what_becomes_non_comparable": "future claims that would pretend the carried baseline still supports one more same-class change loop",
            "why_non_marginal_information_gain_still_exists": "",
            "admission_status": "rejected",
            "rejection_reason": "no_honest_next_move_remains_after_evidence_boundary_readout",
        },
        {
            "candidate_id": "governed_methodological_reframing_v1",
            "candidate_family": "governed_methodological_reframing_question",
            "reframing_target": "reframe_what_the_project_is_honestly_trying_to_conclude_after_carried_exhaustion",
            "why_this_is_not_a_silent_restart": "it names a larger methodological question instead of silently replacing tasks or baselines",
            "what_remains_interpretable": "the carried exhaustion result and the reasons the earlier branches no longer open honestly",
            "what_becomes_non_comparable": "ordinary pre_post claims that assume the same evidence object is still the active question",
            "why_non_marginal_information_gain_still_exists": "",
            "admission_status": "rejected",
            "rejection_reason": "no_honest_next_move_remains_after_evidence_boundary_readout",
        },
        {
            "candidate_id": "governed_baseline_reset_with_loss_accounting_v1",
            "candidate_family": "governed_baseline_reset_with_loss_accounting",
            "reframing_target": "reset_the_baseline_only_under_explicit_named_loss_of_comparability",
            "why_this_is_not_a_silent_restart": "the reset is only admitted if its loss of comparability is explicit and governed rather than hidden",
            "what_remains_interpretable": "the carried evidence-boundary result that motivated asking whether a governed reset is honest at all",
            "what_becomes_non_comparable": "same-baseline continuity claims on the original 12-case substrate after reset",
            "why_non_marginal_information_gain_still_exists": "",
            "admission_status": "rejected",
            "rejection_reason": "deferred_until_it_proves_it_is_not_just_a_disguised_restart",
        },
    ]
}

DEFAULT_NEXT_MOVE_VIABILITY_OBJECT = {
    "next_move_viability_status": "not_justified",
    "scope_relevant_uncertainty_remains": False,
    "named_viability_question": "",
    "expected_information_gain": "marginal",
    "concrete_first_pack_available": False,
    "next_move_still_possible": False,
    "named_reason_if_not_justified": (
        "the_carried_evidence_boundary_readout_does_not_leave_a_more_honest_next_move_on_the_same_governed_frontier"
    ),
}

DEFAULT_GOVERNANCE_OUTCOME = {
    "next_move_governance_outcome": "no_honest_next_move_remains",
    "named_governance_outcome_reason": (
        "after_local_and_transition_question_exhaustion_no_larger_reframing_survives_with_non_marginal_information_gain"
    ),
}


def _build_baseline_anchor(*, v112_closeout_path: str, v171_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    builder = v112.get("product_gap_substrate_builder", {})
    v171_conclusion = load_json(v171_closeout_path).get("conclusion", {})
    rows = builder.get("product_gap_candidate_table") or []
    identity = builder.get("carried_baseline_source", "")
    return {
        "baseline_anchor_status": "ready",
        "carried_phase_closeout_version": "v0_17_1",
        "carried_phase_caveat_label": v171_conclusion.get("explicit_caveat_label", ""),
        "carried_next_primary_phase_question": v171_conclusion.get("next_primary_phase_question", ""),
        "carried_product_gap_substrate_identity": identity,
        "carried_product_gap_substrate_size": len(rows),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION
            and len(rows) == EXPECTED_V112_SUBSTRATE_SIZE
            and v171_conclusion.get("explicit_caveat_label") == EXPECTED_V171_CAVEAT
            and v171_conclusion.get("next_primary_phase_question") == EXPECTED_V171_NEXT_PRIMARY_QUESTION
        ),
    }


def _build_evidence_boundary_readout(
    *,
    v161_closeout_path: str,
    v170_closeout_path: str,
    v171_closeout_path: str,
) -> dict:
    v161_conclusion = load_json(v161_closeout_path).get("conclusion", {})
    v170_conclusion = load_json(v170_closeout_path).get("conclusion", {})
    v171_conclusion = load_json(v171_closeout_path).get("conclusion", {})
    local_exhaustion_confirmed = (
        v161_conclusion.get("version_decision") == EXPECTED_V161_VERSION_DECISION
        and v161_conclusion.get("explicit_caveat_label") == EXPECTED_V161_CAVEAT
    )
    transition_exhaustion_confirmed = (
        v170_conclusion.get("version_decision") == EXPECTED_V170_VERSION_DECISION
        and v170_conclusion.get("transition_governance_outcome") == EXPECTED_V170_GOVERNANCE_OUTCOME
        and v171_conclusion.get("explicit_caveat_label") == EXPECTED_V171_CAVEAT
    )
    ready = local_exhaustion_confirmed and transition_exhaustion_confirmed
    return {
        "evidence_boundary_readout_status": "ready" if ready else "partial",
        "carried_local_question_exhaustion_confirmed": local_exhaustion_confirmed,
        "carried_transition_question_exhaustion_confirmed": transition_exhaustion_confirmed,
        "named_boundary_reason": (
            "the_carried_evidence_has_already_exhausted_both_local_and_transition_question_routes"
            if ready
            else ""
        ),
        "what_the_carried_evidence_has_already_answered": (
            "it has already answered that neither further honest local questions nor further honest governed transition questions remain on the same carried baseline"
        ),
        "what_the_carried_evidence_no_longer_honestly_supports": (
            "another same-frontier branch presented as if it were still a new governed question on the carried evidence object"
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
            "candidate_family",
            "concrete_change_surface",
            "gateforge_layer",
            "relative_strength_vs_v0_17",
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
            "reframing_target",
            "why_this_is_not_a_silent_restart",
            "what_remains_interpretable",
            "what_becomes_non_comparable",
            "why_non_marginal_information_gain_still_exists",
            "admission_status",
        ]:
            if row.get(field) in (None, "", []):
                if not (row.get("admission_status") == "rejected" and field == "why_non_marginal_information_gain_still_exists"):
                    missing.append(f"{row.get('candidate_id', 'unknown')}.{field}")
        if row.get("candidate_family") not in known_families:
            missing.append(f"{row.get('candidate_id', 'unknown')}.unknown_family")
        if row.get("admission_status") == "admitted":
            admitted.append(row)
        elif row.get("admission_status") == "rejected":
            rejected.append(row)
            if not row.get("rejection_reason"):
                missing.append(f"{row.get('candidate_id', 'unknown')}.rejection_reason")
    summary = {
        "next_move_registry_status": "frozen" if not missing else "partial",
        "admitted_candidate_count": len(admitted),
        "rejected_candidate_count": len(rejected),
        "named_first_next_move_pack_ids": [row["candidate_id"] for row in admitted],
        "admitted_rows": admitted,
        "rejected_rows": rejected,
        "rejection_reason_table": [
            {"candidate_id": row.get("candidate_id", ""), "rejection_reason": row.get("rejection_reason", "")}
            for row in rejected
        ],
        "next_move_admission_rules_frozen": not missing,
        "missing_fields": missing,
    }
    return summary, admitted, rejected


def _build_viability_object(viability_object: dict | None, admitted_rows: list[dict]) -> dict:
    if viability_object is not None:
        return copy.deepcopy(viability_object)
    return {
        **copy.deepcopy(DEFAULT_NEXT_MOVE_VIABILITY_OBJECT),
        "concrete_first_pack_available": bool(admitted_rows),
    }


def _validate_viability_object(obj: dict) -> tuple[str, list[str]]:
    missing: list[str] = []
    status = obj.get("next_move_viability_status")
    if status not in {"justified", "not_justified", "invalid"}:
        missing.append("next_move_viability_status")
    if obj.get("expected_information_gain") not in {"marginal", "non_marginal"}:
        missing.append("expected_information_gain")
    if obj.get("scope_relevant_uncertainty_remains") not in {True, False}:
        missing.append("scope_relevant_uncertainty_remains")
    if obj.get("concrete_first_pack_available") not in {True, False}:
        missing.append("concrete_first_pack_available")
    if obj.get("next_move_still_possible") not in {True, False}:
        missing.append("next_move_still_possible")
    if status == "justified":
        if obj.get("named_viability_question") in (None, "", []):
            missing.append("named_viability_question")
        justified_ok = all(
            [
                obj.get("scope_relevant_uncertainty_remains") is True,
                obj.get("expected_information_gain") == "non_marginal",
                obj.get("concrete_first_pack_available") is True,
                obj.get("next_move_still_possible") is True,
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
    outcome = obj.get("next_move_governance_outcome")
    if outcome not in {"next_honest_move_exists", "no_honest_next_move_remains", "invalid"}:
        missing.append("next_move_governance_outcome")
    if not obj.get("named_governance_outcome_reason"):
        missing.append("named_governance_outcome_reason")
    return ("ready" if not missing else "partial", missing)


def build_v180_governance_pack(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v161_closeout_path: str = str(DEFAULT_V161_CLOSEOUT_PATH),
    v170_closeout_path: str = str(DEFAULT_V170_CLOSEOUT_PATH),
    v171_closeout_path: str = str(DEFAULT_V171_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    lever_map: dict | None = None,
    family_separation_rule: dict | None = None,
    candidate_registry: dict | None = None,
    next_move_viability_object: dict | None = None,
    governance_outcome: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    baseline_anchor = _build_baseline_anchor(v112_closeout_path=v112_closeout_path, v171_closeout_path=v171_closeout_path)
    evidence_boundary_readout = _build_evidence_boundary_readout(
        v161_closeout_path=v161_closeout_path,
        v170_closeout_path=v170_closeout_path,
        v171_closeout_path=v171_closeout_path,
    )
    continuity_check = _build_baseline_continuity_check(v112_closeout_path=v112_closeout_path, continuity_check_mode=continuity_check_mode)
    lever_map_payload = copy.deepcopy(lever_map or DEFAULT_LEVER_MAP)
    family_separation_payload = copy.deepcopy(family_separation_rule or DEFAULT_FAMILY_SEPARATION_RULE)
    registry_payload = copy.deepcopy(candidate_registry or DEFAULT_CANDIDATE_REGISTRY)
    lever_map_status, lever_map_missing = _validate_lever_map(lever_map_payload)
    family_separation_status, family_separation_missing = _validate_family_separation(family_separation_payload)
    registry_summary, admitted_rows, _rejected_rows = _validate_candidate_registry(registry_payload, lever_map_payload)
    viability_payload = _build_viability_object(next_move_viability_object, admitted_rows)
    viability_status, viability_missing = _validate_viability_object(viability_payload)
    governance_outcome_payload = _build_governance_outcome(governance_outcome)
    governance_outcome_status, governance_outcome_missing = _validate_governance_outcome(governance_outcome_payload)

    named_first_next_move_pack_ready = bool(admitted_rows)
    minimum_completion_signal_pass = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            evidence_boundary_readout.get("evidence_boundary_readout_status") == "ready",
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            named_first_next_move_pack_ready,
            viability_payload.get("next_move_viability_status") == "justified",
            governance_outcome_payload.get("next_move_governance_outcome") == "next_honest_move_exists",
        ]
    )
    governance_structure_ready = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            evidence_boundary_readout.get("evidence_boundary_readout_status") == "ready",
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["next_move_registry_status"] == "frozen",
            governance_outcome_status == "ready",
        ]
    )
    governance_ready_for_runtime_execution = minimum_completion_signal_pass

    if minimum_completion_signal_pass:
        governance_status = "governance_ready"
        top_status = "PASS"
    elif governance_structure_ready and governance_outcome_payload.get("next_move_governance_outcome") == "no_honest_next_move_remains":
        governance_status = "governance_ready"
        top_status = "PASS"
    elif baseline_anchor.get("baseline_anchor_pass"):
        governance_status = "governance_partial"
        top_status = "PARTIAL"
    else:
        governance_status = "invalid"
        top_status = "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_next_honest_move_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "next_honest_move_governance_status": governance_status,
        "next_move_baseline_anchor": baseline_anchor,
        "evidence_boundary_readout": evidence_boundary_readout,
        "baseline_continuity_check": continuity_check,
        "next_move_lever_map": {
            "lever_map_status": lever_map_status,
            "lever_rows": lever_map_payload,
            "missing_fields": lever_map_missing,
        },
        "next_move_family_separation_rule": {
            **family_separation_payload,
            "family_separation_status": family_separation_status,
            "missing_fields": family_separation_missing,
        },
        "next_move_admission": registry_summary,
        "next_move_viability": {
            **viability_payload,
            "viability_object_status": viability_status,
            "missing_fields": viability_missing,
        },
        "governance_outcome": {
            **governance_outcome_payload,
            "governance_outcome_status": governance_outcome_status,
            "missing_fields": governance_outcome_missing,
        },
        "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
        "minimum_completion_signal_pass": minimum_completion_signal_pass,
        "named_first_next_move_pack_ready": named_first_next_move_pack_ready,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.18.0 Next Honest Move Governance Pack",
                "",
                f"- next_honest_move_governance_status: `{governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- next_move_viability_status: `{viability_payload['next_move_viability_status']}`",
                f"- next_move_governance_outcome: `{governance_outcome_payload['next_move_governance_outcome']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.18.0 next-honest-move governance pack.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v161-closeout", default=str(DEFAULT_V161_CLOSEOUT_PATH))
    parser.add_argument("--v170-closeout", default=str(DEFAULT_V170_CLOSEOUT_PATH))
    parser.add_argument("--v171-closeout", default=str(DEFAULT_V171_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v180_governance_pack(
        v112_closeout_path=str(args.v112_closeout),
        v161_closeout_path=str(args.v161_closeout),
        v170_closeout_path=str(args.v170_closeout),
        v171_closeout_path=str(args.v171_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "next_honest_move_governance_status": payload["next_honest_move_governance_status"],
                "next_move_viability_status": payload["next_move_viability"]["next_move_viability_status"],
                "next_move_governance_outcome": payload["governance_outcome"]["next_move_governance_outcome"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
