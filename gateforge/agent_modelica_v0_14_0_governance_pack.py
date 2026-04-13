from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_14_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_RUNTIME_STACK_IDENTITY,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V133_CLOSEOUT_PATH,
    EXPECTED_V112_SUBSTRATE_SIZE,
    EXPECTED_V112_VERSION_DECISION,
    EXPECTED_V115_DOMINANT_GAP_FAMILY,
    EXPECTED_V115_FORMAL_LABEL,
    EXPECTED_V133_CAVEAT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_BASELINE_DERIVATIVE_RULE = {
    "default_mainline_anchor": "same_v0_11_2_frozen_12_case_product_gap_substrate",
    "derivative_allowed_only_for_named_broader_change_reason": True,
    "named_reasons": [
        "governed_model_upgrade_compatibility_constraint",
        "broader_change_instrumentation_need",
        "explicit_runtime_safety_sandboxing_requirement",
    ],
    "one_to_one_traceability_required": True,
    "broad_resampling_from_wider_pool_forbidden": True,
    "silent_case_replacement_forbidden": True,
}

DEFAULT_LEVER_MAP = {
    "broader_execution_policy_restructuring": {
        "change_family": "broader_execution_policy_restructuring",
        "concrete_change_surface": "L2_execution_policy_restructuring_beyond_bounded_strategy_hints",
        "gateforge_layer": "L2_planner_and_replan",
        "relative_strength_vs_v0_13_bounded_pack": "broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "broader_failure_diagnosis_restructuring": {
        "change_family": "broader_failure_diagnosis_restructuring",
        "concrete_change_surface": "L3_L4_failure_chain_restructuring_beyond_bounded_bucket_enrichment",
        "gateforge_layer": "L3_L4_diagnosis",
        "relative_strength_vs_v0_13_bounded_pack": "broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
    },
    "governed_model_upgrade_candidate": {
        "change_family": "governed_model_upgrade_candidate",
        "concrete_change_surface": "LLM_backbone_upgrade_under_same_executor_contract",
        "gateforge_layer": "LLM_provider_slot",
        "relative_strength_vs_v0_13_bounded_pack": "broader",
        "in_scope_status": "in_scope",
        "named_reason_if_deferred": "",
        "upgrade_scope": "llm_backbone",
        "why_pre_post_comparison_remains_valid": (
            "The carried 12-case baseline, executor code path, Docker/runtime stack, and comparison protocol remain fixed; "
            "the delta is isolated to the backbone capability source."
        ),
    },
}

DEFAULT_FAMILY_SEPARATION_RULE = {
    "overlap_pairs_checked": [
        "broader_execution_policy_restructuring::broader_failure_diagnosis_restructuring",
        "broader_execution_policy_restructuring::governed_model_upgrade_candidate",
    ],
    "merged_family_table": [],
    "strict_separation_table": [
        {
            "family_name": "broader_execution_policy_restructuring",
            "distinguished_from": "broader_failure_diagnosis_restructuring",
            "rule": "must target L2 execution policy or replan control rather than diagnosis-chain restructuring",
        },
        {
            "family_name": "governed_model_upgrade_candidate",
            "distinguished_from": "broader_execution_policy_restructuring",
            "rule": "must change the backbone capability source while preserving the same executor contract and carried baseline",
        },
    ],
    "family_separation_status": "ready",
}

DEFAULT_CANDIDATE_REGISTRY = {
    "candidate_rows": [
        {
            "candidate_id": "broader_L2_execution_policy_restructuring_v1",
            "candidate_family": "broader_execution_policy_restructuring",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "bounded_strategy_hints_insufficient_to_change_mainline_resolution",
            "expected_effect_type": "mainline_workflow_improvement",
            "broader_change_surface": "L2_execution_policy_restructuring_beyond_bounded_strategy_hints",
            "why_broader_than_v0_13_bounded_pack": "Restructures L2 execution-policy behavior more deeply than the bounded planner-strategy hint surface used in v0.13.1.",
            "why_still_comparable_on_carried_baseline": "Uses the same carried 12-case baseline, same executor shell, and same runtime contract.",
            "admission_status": "admitted",
        },
        {
            "candidate_id": "governed_llm_backbone_upgrade_v1",
            "candidate_family": "governed_model_upgrade_candidate",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "bounded_surface_changes_do_not_reach_backbone_capability_shortfall",
            "expected_effect_type": "mainline_workflow_improvement",
            "broader_change_surface": "LLM_backbone_upgrade_under_same_executor_contract",
            "why_broader_than_v0_13_bounded_pack": "Changes the backbone capability source itself rather than only altering bounded planner or diagnosis surfaces.",
            "why_still_comparable_on_carried_baseline": "Keeps the same carried cases, same executor code path, same Docker/runtime stack, and isolates the delta to backbone scope.",
            "admission_status": "admitted",
        },
        {
            "candidate_id": "broad_unconstrained_model_family_replacement_candidate",
            "candidate_family": "governed_model_upgrade_candidate",
            "target_gap_family": "residual_core_capability_gap",
            "target_failure_mode": "global_underpowered_behavior",
            "expected_effect_type": "mainline_workflow_improvement",
            "broader_change_surface": "full_unconstrained_model_family_replacement",
            "why_broader_than_v0_13_bounded_pack": "Replaces the entire model family without a bounded comparison contract.",
            "why_still_comparable_on_carried_baseline": "",
            "admission_status": "rejected",
            "rejection_reason": "broad_unconstrained_model_family_replacement_out_of_scope",
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


def _build_baseline_anchor(*, v112_closeout_path: str, v115_closeout_path: str, v133_closeout_path: str) -> dict:
    v112 = load_json(v112_closeout_path)
    v112_conclusion = v112.get("conclusion", {})
    v112_builder = v112.get("product_gap_substrate_builder", {})
    v115_conclusion = load_json(v115_closeout_path).get("conclusion", {})
    v133_conclusion = load_json(v133_closeout_path).get("conclusion", {})
    substrate_table = v112_builder.get("product_gap_candidate_table") or []
    substrate_identity = v112_builder.get("carried_baseline_source", "")
    return {
        "baseline_anchor_status": "ready",
        "carried_phase_closeout_version": "v0_13_3",
        "carried_phase_caveat_label": v133_conclusion.get("explicit_caveat_label"),
        "carried_next_primary_phase_question": v133_conclusion.get("next_primary_phase_question"),
        "carried_product_gap_substrate_identity": substrate_identity,
        "carried_product_gap_substrate_size": len(substrate_table),
        "carried_product_gap_formal_label": v115_conclusion.get("formal_adjudication_label"),
        "carried_dominant_gap_family_readout": v115_conclusion.get("dominant_gap_family_readout"),
        "baseline_derivative_rule_frozen": copy.deepcopy(DEFAULT_BASELINE_DERIVATIVE_RULE),
        "baseline_anchor_pass": (
            v112_conclusion.get("version_decision") == EXPECTED_V112_VERSION_DECISION
            and len(substrate_table) == EXPECTED_V112_SUBSTRATE_SIZE
            and v115_conclusion.get("formal_adjudication_label") == EXPECTED_V115_FORMAL_LABEL
            and v115_conclusion.get("dominant_gap_family_readout") == EXPECTED_V115_DOMINANT_GAP_FAMILY
            and bool(v133_conclusion.get("explicit_caveat_present"))
            and v133_conclusion.get("explicit_caveat_label") == EXPECTED_V133_CAVEAT
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
            "relative_strength_vs_v0_13_bounded_pack",
            "in_scope_status",
        ]:
            if row.get(field) in (None, "", []):
                missing.append(f"{family_name}.{field}")
        if family_name == "governed_model_upgrade_candidate":
            for field in ["upgrade_scope", "why_pre_post_comparison_remains_valid"]:
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
            "broader_change_surface",
            "why_broader_than_v0_13_bounded_pack",
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
        "broader_change_registry_status": "frozen" if not missing and admitted else "partial",
        "admitted_candidate_count": len(admitted),
        "rejected_candidate_count": len(rejected),
        "named_first_broader_change_pack_ids": [row["candidate_id"] for row in admitted],
        "admitted_rows": admitted,
        "rejected_rows": rejected,
        "rejection_reason_table": [
            {"candidate_id": row.get("candidate_id", ""), "rejection_reason": row.get("rejection_reason", "")}
            for row in rejected
        ],
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


def build_v140_governance_pack(
    *,
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v133_closeout_path: str = str(DEFAULT_V133_CLOSEOUT_PATH),
    continuity_check_mode: str = "schema_only",
    lever_map: dict | None = None,
    family_separation_rule: dict | None = None,
    candidate_registry: dict | None = None,
    comparison_protocol: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    baseline_anchor = _build_baseline_anchor(
        v112_closeout_path=v112_closeout_path,
        v115_closeout_path=v115_closeout_path,
        v133_closeout_path=v133_closeout_path,
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

    named_first_broader_change_pack_ready = bool(admitted_rows)
    minimum_completion_signal_pass = all(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") == "ready",
            lever_map_status == "ready",
            family_separation_status == "ready",
            registry_summary["broader_change_registry_status"] == "frozen",
            comparison_protocol_ready,
            named_first_broader_change_pack_ready,
        ]
    )
    governance_ready_for_runtime_execution = minimum_completion_signal_pass

    governance_signals_present = any(
        [
            baseline_anchor.get("baseline_anchor_pass"),
            continuity_check.get("baseline_continuity_check_status") in {"ready", "broken"},
            lever_map_status in {"ready", "partial"},
            family_separation_status in {"ready", "partial"},
            registry_summary["broader_change_registry_status"] in {"frozen", "partial"},
            comparison_protocol_ready or bool(comparison_protocol_missing),
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
        "schema_version": f"{SCHEMA_PREFIX}_broader_change_governance_pack",
        "generated_at_utc": now_utc(),
        "status": top_status,
        "capability_broader_change_governance_status": governance_status,
        "broader_change_baseline_anchor": baseline_anchor,
        "baseline_continuity_check": continuity_check,
        "broader_change_lever_map": {
            "lever_map_status": lever_map_status,
            "missing_fields": lever_map_missing,
            "lever_rows": lever_map_payload,
        },
        "broader_change_family_separation_rule": {
            **family_separation_payload,
            "family_separation_status": family_separation_status,
            "missing_fields": family_separation_missing,
        },
        "broader_change_admission": {
            **registry_summary,
            "broader_change_admission_rules_frozen": registry_summary["broader_change_registry_status"] == "frozen",
        },
        "pre_post_broader_change_comparison_protocol": {
            **comparison_protocol_payload,
            "comparison_protocol_status": "ready" if comparison_protocol_ready else "partial",
            "comparison_protocol_missing_fields": comparison_protocol_missing,
        },
        "governance_ready_for_runtime_execution": governance_ready_for_runtime_execution,
        "minimum_completion_signal_pass": minimum_completion_signal_pass,
        "named_first_broader_change_pack_ready": named_first_broader_change_pack_ready,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.0 Broader Change Governance Pack",
                "",
                f"- capability_broader_change_governance_status: `{governance_status}`",
                f"- governance_ready_for_runtime_execution: `{governance_ready_for_runtime_execution}`",
                f"- named_first_broader_change_pack_ready: `{named_first_broader_change_pack_ready}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.0 broader-change governance pack.")
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v133-closeout", default=str(DEFAULT_V133_CLOSEOUT_PATH))
    parser.add_argument("--continuity-check-mode", default="schema_only")
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v140_governance_pack(
        v112_closeout_path=str(args.v112_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v133_closeout_path=str(args.v133_closeout),
        continuity_check_mode=str(args.continuity_check_mode),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "capability_broader_change_governance_status": payload.get("capability_broader_change_governance_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
