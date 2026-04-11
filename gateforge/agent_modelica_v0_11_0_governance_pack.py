from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_v0_11_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_PROTOCOL_CONTRACT_VERSION,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V108_CLOSEOUT_PATH,
    EXPECTED_PATCH_CANDIDATE_NAMES,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


DEFAULT_CONTEXT_CONTRACT = {
    "append_only_context_elements": [
        "user_task_statement",
        "workflow_goal",
        "tool_call_history",
        "artifact_history",
    ],
    "recoverable_external_state_elements": [
        "workspace_files",
        "artifact_json_paths",
        "omc_error_logs",
    ],
    "non_compressible_trace_elements": [
        "workflow_goal",
        "full_omc_error_output",
        "verifier_failure_trace",
    ],
    "forbidden_context_rewrites": [
        "rewrite_or_drop_workflow_goal_in_place",
        "replace_failed_tool_output_with_unattributed_summary",
        "silently_remove_prior_attempt_trace",
    ],
    "goal_reanchoring_rule": "Before each OMC call, restate the task workflow_goal verbatim in the live prompt context.",
    "error_propagation_rule": "Carry full actionable OMC error content into the next round unless it is preserved by explicit artifact path.",
}

DEFAULT_ANTI_REWARD_HACKING_CHECKLIST = {
    "future_information_leakage_check": "Disallow direct or indirect access to future answer artifacts, mutation ground truth, or evaluator-only state.",
    "fake_success_artifact_check": "Detect success claims that depend on file existence or test-harness modification rather than true model repair.",
    "evaluator_rule_exploitation_check": "Detect attempts to satisfy the evaluator through rule shaping rather than legitimate workflow completion.",
    "prohibited_shortcut_retrieval_check": "Disallow prohibited retrieval paths that import hidden answers or externally cached success states.",
    "prompt_injection_via_tool_or_env_output_check": "Treat tool and environment outputs as untrusted and auditable rather than authoritative instructions.",
}

DEFAULT_PRODUCT_GAP_SIDECAR = {
    "scaffold_version": "gateforge_live_executor_v1_scaffold",
    "protocol_contract_version": CURRENT_PROTOCOL_CONTRACT_VERSION,
    "token_count": {"type": "integer", "minimum": 0},
    "context_contract_version": "v0_11_0_context_contract_v1",
    "anti_reward_hacking_checklist_version": "v0_11_0_anti_reward_hacking_checklist_v1",
    "sidecar_observation_fields": [
        "workflow_goal_reanchoring_observed",
        "system_prompt_dynamic_field_audit_result",
        "full_omc_error_propagation_observed",
    ],
}

DEFAULT_PROTOCOL_ROBUSTNESS_SCOPE = {
    "in_scope_scaffold_variants": [
        "gateforge_live_executor_v1_scaffold",
    ],
    "in_scope_protocol_variants": [
        CURRENT_PROTOCOL_CONTRACT_VERSION,
    ],
    "deferred_variants": [
        "alternate_executor_shells",
        "cross_scaffold_product_shells",
    ],
    "baseline_protocol_variant": CURRENT_MAIN_EXECUTION_CHAIN,
}

DEFAULT_PATCH_CANDIDATES = {
    "workflow_goal_reanchoring_patch_candidate": {
        "candidate_name": "workflow_goal_reanchoring_patch_candidate",
        "target_problem": "Long-horizon workflow-goal drift before OMC calls leads to surface-fix behavior.",
        "expected_effect": "Reduce surface_fix_only_rate and improve workflow-goal retention in later product-gap traces.",
    },
    "system_prompt_dynamic_field_audit_patch_candidate": {
        "candidate_name": "system_prompt_dynamic_field_audit_patch_candidate",
        "target_problem": "Dynamic fields in the system-prompt region destabilize the static prefix and waste cache / latency budget.",
        "expected_effect": "Improve cache-prefix stability and reduce avoidable protocol or latency overhead.",
    },
    "full_omc_error_propagation_audit_patch_candidate": {
        "candidate_name": "full_omc_error_propagation_audit_patch_candidate",
        "target_problem": "Loss or truncation of actionable OMC error content across rounds prevents adaptive repair behavior.",
        "expected_effect": "Improve adaptation after failed runs and reduce repeated non-adaptive retries on the same error state.",
    },
}


def _build_baseline_anchor(
    *,
    v103_closeout_path: str,
    v104_closeout_path: str,
    v106_closeout_path: str,
    v108_closeout_path: str,
) -> dict:
    v103 = load_json(v103_closeout_path).get("conclusion", {})
    v104 = load_json(v104_closeout_path).get("conclusion", {})
    v106 = load_json(v106_closeout_path).get("conclusion", {})
    v108 = load_json(v108_closeout_path).get("conclusion", {})

    derivative_rule = {
        "default_mainline_anchor": "same_v0_10_3_frozen_12_case_real_origin_substrate",
        "derivative_allowed_only_for_named_product_boundary_reason": True,
        "named_reasons": [
            "protocol_scope_incompatibility",
            "shell_specific_observability_requirement",
            "instrumentation_only_transformation",
        ],
        "one_to_one_traceability_required": True,
        "broad_resampling_from_wider_v0_10_pool_forbidden": True,
        "silent_case_replacement_forbidden": True,
    }

    return {
        "baseline_substrate_version": "v0_10_3",
        "baseline_profile_version": "v0_10_4",
        "baseline_threshold_version": "v0_10_5",
        "baseline_adjudication_version": "v0_10_6",
        "baseline_phase_closeout_version": "v0_10_8",
        "baseline_substrate_identity": "same_v0_10_3_frozen_12_case_real_origin_substrate",
        "baseline_profile_route": v104.get("version_decision"),
        "baseline_adjudication_label": v106.get("final_adjudication_label"),
        "baseline_explicit_caveat_label": v108.get("explicit_caveat_label"),
        "baseline_derivative_rule_frozen": derivative_rule,
        "baseline_anchor_pass": (
            v103.get("version_decision") == "v0_10_3_first_real_origin_workflow_substrate_ready"
            and v103.get("real_origin_substrate_size") == 12
            and v104.get("version_decision") == "v0_10_4_first_real_origin_workflow_profile_characterized"
            and v106.get("version_decision") == "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable"
            and v108.get("version_decision") == "v0_10_phase_nearly_complete_with_explicit_caveat"
        ),
    }


def _validate_context_contract(contract: dict) -> tuple[str, list[str]]:
    missing = []
    for field in [
        "append_only_context_elements",
        "recoverable_external_state_elements",
        "non_compressible_trace_elements",
        "forbidden_context_rewrites",
        "goal_reanchoring_rule",
        "error_propagation_rule",
    ]:
        value = contract.get(field)
        if isinstance(value, list):
            if not value:
                missing.append(field)
        elif not value:
            missing.append(field)
    return ("ready" if not missing else "partial", missing)


def _validate_anti_reward_hacking(checklist: dict) -> tuple[str, list[str]]:
    missing = []
    for field in [
        "future_information_leakage_check",
        "fake_success_artifact_check",
        "evaluator_rule_exploitation_check",
        "prohibited_shortcut_retrieval_check",
        "prompt_injection_via_tool_or_env_output_check",
    ]:
        if not checklist.get(field):
            missing.append(field)
    return ("ready" if not missing else "partial", missing)


def _validate_product_gap_sidecar(sidecar: dict) -> tuple[str, list[str]]:
    missing = []
    for field in [
        "scaffold_version",
        "protocol_contract_version",
        "token_count",
        "context_contract_version",
        "anti_reward_hacking_checklist_version",
        "sidecar_observation_fields",
    ]:
        value = sidecar.get(field)
        if isinstance(value, list):
            if not value:
                missing.append(field)
        elif value in (None, "", {}):
            missing.append(field)
    return ("ready" if not missing else "partial", missing)


def _validate_protocol_scope(scope: dict) -> tuple[str, list[str]]:
    missing = []
    for field in [
        "in_scope_scaffold_variants",
        "in_scope_protocol_variants",
        "deferred_variants",
        "baseline_protocol_variant",
    ]:
        value = scope.get(field)
        if isinstance(value, list):
            if not value:
                missing.append(field)
        elif not value:
            missing.append(field)
    if scope.get("baseline_protocol_variant") != CURRENT_MAIN_EXECUTION_CHAIN:
        missing.append("baseline_protocol_variant_must_name_current_main_execution_chain")
    return ("ready" if not missing else "partial", missing)


def _validate_patch_candidates(candidates: dict) -> tuple[str, list[str]]:
    missing = []
    if set(candidates.keys()) != EXPECTED_PATCH_CANDIDATE_NAMES:
        missing.append("patch_candidate_keyset")
    for key in EXPECTED_PATCH_CANDIDATE_NAMES:
        candidate = candidates.get(key)
        if not isinstance(candidate, dict):
            missing.append(f"{key}.object")
            continue
        for field in ["candidate_name", "target_problem", "expected_effect"]:
            if not candidate.get(field):
                missing.append(f"{key}.{field}")
    return ("ready" if not missing else "partial", missing)


def build_v110_governance_pack(
    *,
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v108_closeout_path: str = str(DEFAULT_V108_CLOSEOUT_PATH),
    context_contract: dict | None = None,
    anti_reward_hacking_checklist: dict | None = None,
    product_gap_sidecar: dict | None = None,
    protocol_robustness_scope: dict | None = None,
    patch_candidates: dict | None = None,
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)

    context_contract_payload = copy.deepcopy(context_contract or DEFAULT_CONTEXT_CONTRACT)
    anti_reward_hacking_payload = copy.deepcopy(
        anti_reward_hacking_checklist or DEFAULT_ANTI_REWARD_HACKING_CHECKLIST
    )
    product_gap_sidecar_payload = copy.deepcopy(product_gap_sidecar or DEFAULT_PRODUCT_GAP_SIDECAR)
    protocol_robustness_scope_payload = copy.deepcopy(protocol_robustness_scope or DEFAULT_PROTOCOL_ROBUSTNESS_SCOPE)
    patch_candidates_payload = copy.deepcopy(patch_candidates or DEFAULT_PATCH_CANDIDATES)

    context_status, context_missing = _validate_context_contract(context_contract_payload)
    anti_status, anti_missing = _validate_anti_reward_hacking(anti_reward_hacking_payload)
    sidecar_status, sidecar_missing = _validate_product_gap_sidecar(product_gap_sidecar_payload)
    scope_status, scope_missing = _validate_protocol_scope(protocol_robustness_scope_payload)
    patch_status, patch_missing = _validate_patch_candidates(patch_candidates_payload)
    baseline_anchor = _build_baseline_anchor(
        v103_closeout_path=v103_closeout_path,
        v104_closeout_path=v104_closeout_path,
        v106_closeout_path=v106_closeout_path,
        v108_closeout_path=v108_closeout_path,
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_governance_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "context_contract": {
            **context_contract_payload,
            "context_contract_status": context_status,
            "missing_fields": context_missing,
        },
        "anti_reward_hacking_checklist": {
            **anti_reward_hacking_payload,
            "checklist_status": anti_status,
            "missing_fields": anti_missing,
        },
        "product_gap_sidecar": {
            **product_gap_sidecar_payload,
            "product_gap_sidecar_status": sidecar_status,
            "missing_fields": sidecar_missing,
        },
        "protocol_robustness_scope": {
            **protocol_robustness_scope_payload,
            "scope_status": scope_status,
            "missing_fields": scope_missing,
        },
        "patch_candidates": {
            **patch_candidates_payload,
            "patch_candidate_pack_status": patch_status,
            "missing_fields": patch_missing,
        },
        "baseline_anchor": baseline_anchor,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.0 Product-Gap Governance Pack",
                "",
                f"- context_contract_status: `{context_status}`",
                f"- anti_reward_hacking_checklist_status: `{anti_status}`",
                f"- product_gap_sidecar_status: `{sidecar_status}`",
                f"- protocol_robustness_scope_status: `{scope_status}`",
                f"- patch_candidate_pack_status: `{patch_status}`",
                f"- baseline_anchor_pass: `{baseline_anchor['baseline_anchor_pass']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.0 product-gap governance pack artifact.")
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v108-closeout", default=str(DEFAULT_V108_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v110_governance_pack(
        v103_closeout_path=str(args.v103_closeout),
        v104_closeout_path=str(args.v104_closeout),
        v106_closeout_path=str(args.v106_closeout),
        v108_closeout_path=str(args.v108_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "baseline_anchor_pass": payload.get("baseline_anchor", {}).get("baseline_anchor_pass")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
