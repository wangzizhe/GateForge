from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_rule_engine_v1 import (
    RuleContext as _RuleContext,
    apply_parse_error_pre_repair as _rule_engine_apply_parse_error_pre_repair,
    apply_simulate_error_injection_repair as _rule_engine_apply_simulate_error_injection_repair,
    apply_multi_round_layered_repair as _rule_engine_apply_multi_round_layered_repair,
    apply_wave2_1_marker_repair as _rule_engine_apply_wave2_1_marker_repair,
    apply_wave2_2_marker_repair as _rule_engine_apply_wave2_2_marker_repair,
    apply_wave2_marker_repair as _rule_engine_apply_wave2_marker_repair,
    build_default_rule_registry as _build_default_rule_registry,
    build_failure_type_rule_priority_context as _build_failure_type_rule_priority_context,
    multi_round_deterministic_repair_enabled as _rule_engine_multi_round_deterministic_repair_enabled,
    wave2_1_deterministic_repair_enabled as _rule_engine_wave2_1_deterministic_repair_enabled,
    wave2_2_deterministic_repair_enabled as _rule_engine_wave2_2_deterministic_repair_enabled,
    wave2_deterministic_repair_enabled as _rule_engine_wave2_deterministic_repair_enabled,
)
from .agent_modelica_repair_action_policy_v0 import (
    build_multistep_llm_plan_prompt_hints_v1,
    build_multistep_repair_plan_v0,
    recommend_repair_actions_v0,
)
from .agent_modelica_l4_guided_search_engine_v1 import (
    adaptive_parameter_target_pools as _adaptive_parameter_target_pools,
    apply_behavioral_robustness_source_blind_local_repair as _l4_apply_behavioral_robustness_source_blind_local_repair,
    apply_source_blind_multistep_branch_escape_search as _apply_source_blind_multistep_branch_escape_search,
    apply_source_blind_multistep_exposure_repair as _apply_source_blind_multistep_exposure_repair,
    apply_source_blind_multistep_llm_plan as _apply_source_blind_multistep_llm_plan,
    apply_source_blind_multistep_llm_resolution as _apply_source_blind_multistep_llm_resolution,
    apply_source_blind_multistep_local_search as _apply_source_blind_multistep_local_search,
    apply_simulate_error_parameter_recovery as _apply_simulate_error_parameter_recovery,
    apply_source_blind_multistep_stage2_local_repair as _apply_source_blind_multistep_stage2_local_repair,
    behavioral_robustness_local_repair_clusters as _behavioral_robustness_local_repair_clusters,
    build_adaptive_search_candidates as _build_adaptive_search_candidates,
    build_guided_search_execution_plan as _build_guided_search_execution_plan,
    build_guided_search_observation_payload as _build_guided_search_observation_payload,
    guard_robustness_patch as _guard_robustness_patch,
    llm_plan_branch_match as _llm_plan_branch_match,
    llm_plan_parameter_match as _llm_plan_parameter_match,
    normalize_source_blind_multistep_llm_plan as _normalize_source_blind_multistep_llm_plan,
    preferred_llm_parameter_order_for_branch as _preferred_llm_parameter_order_for_branch,
    resolve_llm_plan_parameter_names as _resolve_llm_plan_parameter_names,
    robustness_structure_signature as _robustness_structure_signature,
    select_initial_llm_plan_parameters as _select_initial_llm_plan_parameters,
    source_blind_multistep_branch_escape_templates as _source_blind_multistep_branch_escape_templates,
    source_blind_multistep_exposure_clusters as _source_blind_multistep_exposure_clusters,
    source_blind_multistep_llm_resolution_targets as _source_blind_multistep_llm_resolution_targets,
    source_blind_multistep_local_search_templates as _source_blind_multistep_local_search_templates,
    source_blind_multistep_stage2_resolution_clusters as _source_blind_multistep_stage2_resolution_clusters,
)
from .agent_modelica_stage_branch_controller_v1 import (
    behavioral_contract_bucket as _behavioral_contract_bucket,
    build_multistep_eval as _build_multistep_eval,
    multistep_stage_default_focus as _multistep_stage_default_focus,
    multistep_branch_mode as _multistep_branch_mode,
    looks_like_stage_1_focus as _looks_like_stage_1_focus,
    build_multistep_stage_context as _build_multistep_stage_context,
    stage_plan_fields as _stage_plan_fields,
    extract_source_blind_multistep_markers as _extract_source_blind_multistep_markers,
    build_source_blind_multistep_llm_context as _build_source_blind_multistep_llm_context,
    count_passed_scenarios as _count_passed_scenarios,
    build_source_blind_multistep_llm_replan_context as _build_source_blind_multistep_llm_replan_context,
    build_source_blind_multistep_replan_budget as _build_source_blind_multistep_replan_budget,
    build_branching_stage_2_eval as _build_branching_stage_2_eval,
    make_multistep_memory,
)
from .agent_modelica_text_repair_utils_v1 import (
    apply_regex_replacement_cluster as _apply_regex_replacement_cluster,
    extract_named_numeric_values as _extract_named_numeric_values,
    find_primary_model_name as _find_primary_model_name,
    format_numeric_candidate as _format_numeric_candidate,
)
from .agent_modelica_behavioral_contract_evaluator_v1 import (
    BEHAVIORAL_MARKER_PREFIX,
    BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX,
    apply_initialization_marker_repair as _apply_initialization_marker_repair,
    evaluate_behavioral_contract_from_model_text as _evaluate_behavioral_contract_from_model_text,
    normalize_behavioral_contract_text as _normalize_behavioral_contract_text,
)
from .agent_modelica_semantic_time_constant_oracle_v1 import (
    evaluate_semantic_time_constant_contract as _evaluate_semantic_time_constant_contract,
)
from .agent_modelica_omc_workspace_v1 import (
    WorkspaceModelLayout as _WorkspaceModelLayout,
    classify_failure as _classify_failure,
    cleanup_workspace_best_effort as _cleanup_workspace_best_effort,
    copytree_best_effort as _copytree_best_effort,
    extract_om_success_flags as _extract_om_success_flags,
    norm_path_text as _norm_path_text,
    prepare_workspace_model_layout as _prepare_workspace_model_layout,
    rel_mos_path as _rel_mos_path,
    run_check_and_simulate as _run_check_and_simulate,
    run_cmd as _run_cmd,
    run_omc_script_docker as _run_omc_script_docker,
    run_omc_script_local as _run_omc_script_local,
    temporary_workspace as _temporary_workspace,
)
from .agent_modelica_l2_plan_replan_engine_v1 import (
    MULTISTEP_PLANNER_CONTRACT_VERSION,
    behavioral_robustness_source_mode as _behavioral_robustness_source_mode,
    bootstrap_env_from_repo as _bootstrap_env_from_repo,
    build_source_blind_multistep_planner_contract as _build_source_blind_multistep_planner_contract,
    build_source_blind_multistep_planner_prompt as _build_source_blind_multistep_planner_prompt,
    gemini_repair_model_text as _gemini_repair_model_text,
    llm_generate_repair_plan as _llm_generate_repair_plan,
    llm_repair_model_text as _llm_repair_model_text,
    llm_round_constraints as _llm_round_constraints,
    openai_repair_model_text as _openai_repair_model_text,
    parse_env_assignment as _parse_env_assignment,
    planner_adapter_for_provider as _planner_adapter_for_provider,
    planner_family_for_provider as _planner_family_for_provider,
    resolve_llm_provider as _resolve_llm_provider,
    send_with_budget as _send_with_budget,
)
from .agent_modelica_experience_writer_v1 import build_experience_record as _build_experience_record
from .agent_modelica_experience_replay_v1 import (
    build_rule_priority_context as _build_rule_priority_context,
    summarize_signal_coverage as _summarize_signal_coverage,
)
from .agent_modelica_planner_experience_context_v1 import (
    build_planner_experience_context as _build_planner_experience_context,
)
from .agent_modelica_operation_policy_v1 import (
    is_planner_event as _is_planner_event,
    operation_summary as _operation_summary,
)
from .agent_modelica_operation_taxonomy_v1 import (
    get_operation as _get_operation,
)
from .agent_modelica_repair_checkpoint_v1 import (
    CheckpointManager as _CheckpointManager,
    checkpoint_summary as _checkpoint_summary,
)
from .agent_modelica_repair_rollback_policy_v1 import (
    ROLLBACK_REASON_NONE as _ROLLBACK_REASON_NONE,
    rollback_reason as _rollback_reason,
)
from .agent_modelica_repair_safety_classifier_v1 import (
    classify_repair_safety as _classify_repair_safety,
)
from .agent_modelica_prompt_input_hygiene_v1 import (
    default_context_truncation_summary as _default_context_truncation_summary,
    truncate_planner_experience_context as _truncate_planner_experience_context,
    truncate_replan_context_for_prompt as _truncate_replan_context_for_prompt,
)
from .agent_modelica_repair_quality_score_v1 import compute_repair_quality_breakdown as _compute_repair_quality_breakdown
from .agent_modelica_v0_3_14_step_experience_common import (
    residual_signal_cluster as _build_v0_3_14_residual_signal_cluster,
)
from .llm_budget import (
    _IN_MEMORY_LIVE_LEDGER,
    _live_budget_config,
    _llm_request_timeout_sec,
    _load_live_ledger,
    _record_live_request_429,
    _reserve_live_request,
)

DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"
PRODUCT_GAP_SCAFFOLD_VERSION = "gateforge_live_executor_v1_scaffold"
PRODUCT_GAP_PROTOCOL_CONTRACT_VERSION = "gateforge_live_executor_v1_contract"
PRODUCT_GAP_CONTEXT_CONTRACT_VERSION = "v0_11_0_context_contract_v1"
PRODUCT_GAP_ANTI_REWARD_HACKING_CHECKLIST_VERSION = "v0_11_0_anti_reward_hacking_checklist_v1"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _diagnostic_context_hints_from_model(*, failure_type: str, expected_stage: str, model_text: str) -> list[str]:
    hints: list[str] = []
    for value in (failure_type, expected_stage):
        text = str(value or "").strip().lower()
        if text:
            hints.append(text)
    lower = str(model_text or "").lower()
    if "gateforge_underconstrained_probe_" in lower:
        hints.extend(["free_variable_probe", "structural_underconstraint"])
    if "gateforge_initialization_infeasible_" in lower:
        hints.extend(["initialization_trigger", "forced_initialization_failure"])
    if "when initial()" in lower:
        hints.append("when_initial_assert")
    if "gateforge_overconstrained_system" in lower:
        hints.extend(["duplicate_equation", "overconstrained_system"])
    if "gateforge_parameter_binding_error" in lower:
        hints.extend(["parameter_binding_error", "invalid_parameter_binding"])
    if "gateforge_array_dimension_mismatch" in lower:
        hints.extend(["array_dimension_mismatch", "invalid_array_binding"])
    if "gateforge_solver_sensitive_simulate_failure" in lower:
        hints.extend(["solver_sensitive_simulate_failure", "stiff_solver_dynamics"])
    if "gateforge_event_logic_error" in lower:
        hints.extend(["event_logic_error", "event_threshold_chattering"])
    if "gateforge_semantic_drift_after_compile_pass" in lower:
        hints.extend(["semantic_drift_after_compile_pass", "dynamic_sign_drift"])
    if "gateforge_cross_component_parameter_coupling_error" in lower:
        hints.extend(["cross_component_parameter_coupling_error", "cross_component_parameter_coupling"])
    if "gateforge_control_loop_sign_semantic_drift" in lower:
        hints.extend(["control_loop_sign_semantic_drift", "control_loop_positive_feedback"])
    if "gateforge_mode_switch_guard_logic_error" in lower:
        hints.extend(["mode_switch_guard_logic_error", "mode_switch_threshold_guard"])
    if "gateforge_cascading_structural_failure" in lower:
        hints.extend(["cascading_structural_failure", "cascading_failure"])
    if "gateforge_coupled_conflict_failure" in lower:
        hints.extend(["coupled_conflict_failure", "paired_conflict"])
    if "gateforge_false_friend_patch_trap" in lower:
        hints.extend(["false_friend_patch_trap", "false_friend_trap"])
    if BEHAVIORAL_MARKER_PREFIX in lower:
        hints.append("behavioral_contract_violation")
    if "steady_state_target_violation" in lower:
        hints.extend(["steady_state_target_violation", "steady_state_contract_miss"])
    if "transient_response_contract_violation" in lower:
        hints.extend(["transient_response_contract_violation", "transient_contract_miss"])
    if "mode_transition_contract_violation" in lower:
        hints.extend(["mode_transition_contract_violation", "mode_transition_contract_miss"])
    if "param_perturbation_robustness_violation" in lower:
        hints.extend(["param_perturbation_robustness_violation", "param_sensitivity_miss", "single_case_only"])
    if "initial_condition_robustness_violation" in lower:
        hints.extend(["initial_condition_robustness_violation", "initial_condition_miss", "single_case_only"])
    if "scenario_switch_robustness_violation" in lower:
        hints.extend(["scenario_switch_robustness_violation", "scenario_switch_miss", "single_case_only"])
    if "stability_then_behavior" in lower:
        hints.extend(["stability_then_behavior", "stability_margin_miss", "behavior_contract_miss"])
    if "behavior_then_robustness" in lower:
        hints.extend(["behavior_then_robustness", "behavior_contract_miss", "single_case_only"])
    if "switch_then_recovery" in lower:
        hints.extend(["switch_then_recovery", "scenario_switch_miss", "post_switch_recovery_miss"])
    return hints


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _apply_source_model_repair(
    *,
    current_text: str,
    source_model_text: str,
    declared_failure_type: str,
    observed_failure_type: str,
) -> tuple[str, dict]:
    declared = str(declared_failure_type or "").strip().lower()
    if declared not in {
        "connector_mismatch",
        "overconstrained_system",
        "parameter_binding_error",
        "array_dimension_mismatch",
        "solver_sensitive_simulate_failure",
        "event_logic_error",
        "semantic_drift_after_compile_pass",
        "cross_component_parameter_coupling_error",
        "control_loop_sign_semantic_drift",
        "mode_switch_guard_logic_error",
        "cascading_structural_failure",
        "coupled_conflict_failure",
        "false_friend_patch_trap",
        "steady_state_target_violation",
        "transient_response_contract_violation",
        "mode_transition_contract_violation",
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    if declared in {"overconstrained_system", "parameter_binding_error", "array_dimension_mismatch"} and not _wave2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_deterministic_repair_disabled"}
    if declared in {"solver_sensitive_simulate_failure", "event_logic_error", "semantic_drift_after_compile_pass"} and not _wave2_1_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_1_deterministic_repair_disabled"}
    if declared in {"cross_component_parameter_coupling_error", "control_loop_sign_semantic_drift", "mode_switch_guard_logic_error"} and not _wave2_2_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "wave2_2_deterministic_repair_disabled"}
    if declared in {"cascading_structural_failure", "coupled_conflict_failure", "false_friend_patch_trap"} and not _multi_round_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "multi_round_deterministic_repair_disabled"}
    if declared in {"steady_state_target_violation", "transient_response_contract_violation", "mode_transition_contract_violation"} and not _behavioral_contract_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "behavioral_contract_deterministic_repair_disabled"}
    if declared in {"param_perturbation_robustness_violation", "initial_condition_robustness_violation", "scenario_switch_robustness_violation"} and not _behavioral_robustness_deterministic_repair_enabled():
        return current_text, {"applied": False, "reason": "behavioral_robustness_deterministic_repair_disabled"}
    if (
        declared in {"param_perturbation_robustness_violation", "initial_condition_robustness_violation", "scenario_switch_robustness_violation"}
        and _behavioral_robustness_source_mode() != "source_aware"
    ):
        return current_text, {"applied": False, "reason": "behavioral_robustness_source_blind_disables_source_repair"}
    source_text = str(source_model_text or "")
    if not source_text.strip():
        return current_text, {"applied": False, "reason": "source_model_text_missing"}
    if str(current_text or "") == source_text:
        return current_text, {"applied": False, "reason": "current_text_matches_source"}
    observed = str(observed_failure_type or "").strip().lower()
    reason = "restored_source_model_text"
    if declared == "parameter_binding_error":
        reason = "restored_source_model_text_for_parameter_binding_error"
    elif declared == "overconstrained_system":
        reason = "restored_source_model_text_for_overconstrained_system"
    elif declared == "array_dimension_mismatch":
        reason = "restored_source_model_text_for_array_dimension_mismatch"
    elif declared == "solver_sensitive_simulate_failure":
        reason = "restored_source_model_text_for_solver_sensitive_simulate_failure"
    elif declared == "event_logic_error":
        reason = "restored_source_model_text_for_event_logic_error"
    elif declared == "semantic_drift_after_compile_pass":
        reason = "restored_source_model_text_for_semantic_drift_after_compile_pass"
    elif declared == "cross_component_parameter_coupling_error":
        reason = "restored_source_model_text_for_cross_component_parameter_coupling_error"
    elif declared == "control_loop_sign_semantic_drift":
        reason = "restored_source_model_text_for_control_loop_sign_semantic_drift"
    elif declared == "mode_switch_guard_logic_error":
        reason = "restored_source_model_text_for_mode_switch_guard_logic_error"
    elif declared == "cascading_structural_failure":
        reason = "restored_source_model_text_for_cascading_structural_failure"
    elif declared == "coupled_conflict_failure":
        reason = "restored_source_model_text_for_coupled_conflict_failure"
    elif declared == "false_friend_patch_trap":
        reason = "restored_source_model_text_for_false_friend_patch_trap"
    elif declared == "steady_state_target_violation":
        reason = "restored_source_model_text_for_steady_state_target_violation"
    elif declared == "transient_response_contract_violation":
        reason = "restored_source_model_text_for_transient_response_contract_violation"
    elif declared == "mode_transition_contract_violation":
        reason = "restored_source_model_text_for_mode_transition_contract_violation"
    elif declared == "param_perturbation_robustness_violation":
        reason = "restored_source_model_text_for_param_perturbation_robustness_violation"
    elif declared == "initial_condition_robustness_violation":
        reason = "restored_source_model_text_for_initial_condition_robustness_violation"
    elif declared == "scenario_switch_robustness_violation":
        reason = "restored_source_model_text_for_scenario_switch_robustness_violation"
    elif observed in {"model_check_error", "connector_mismatch"}:
        reason = "restored_source_model_text_for_connector_mismatch"
    else:
        reason = "restored_source_model_text_from_declared_connector_mismatch"
    return source_text, {"applied": True, "reason": reason}


def _wave2_deterministic_repair_enabled() -> bool:
    return _rule_engine_wave2_deterministic_repair_enabled()


def _wave2_1_deterministic_repair_enabled() -> bool:
    return _rule_engine_wave2_1_deterministic_repair_enabled()


def _wave2_2_deterministic_repair_enabled() -> bool:
    return _rule_engine_wave2_2_deterministic_repair_enabled()


def _multi_round_deterministic_repair_enabled() -> bool:
    return _rule_engine_multi_round_deterministic_repair_enabled()


def _behavioral_contract_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _behavioral_robustness_deterministic_repair_enabled() -> bool:
    return str(os.getenv("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR") or "").strip() == "1"


def _apply_wave2_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    return _rule_engine_apply_wave2_marker_repair(
        current_text=current_text,
        declared_failure_type=declared_failure_type,
    )


def _apply_wave2_1_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    return _rule_engine_apply_wave2_1_marker_repair(
        current_text=current_text,
        declared_failure_type=declared_failure_type,
    )


def _apply_wave2_2_marker_repair(*, current_text: str, declared_failure_type: str) -> tuple[str, dict]:
    return _rule_engine_apply_wave2_2_marker_repair(
        current_text=current_text,
        declared_failure_type=declared_failure_type,
    )


def _apply_simulate_error_injection_repair(
    *, current_text: str, declared_failure_type: str
) -> tuple[str, dict]:
    return _rule_engine_apply_simulate_error_injection_repair(
        current_text=current_text,
        declared_failure_type=declared_failure_type,
    )


def _apply_multi_round_layered_repair(
    *,
    current_text: str,
    source_model_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    return _rule_engine_apply_multi_round_layered_repair(
        current_text=current_text,
        source_model_text=source_model_text,
        declared_failure_type=declared_failure_type,
        current_round=current_round,
    )



def _apply_behavioral_robustness_source_blind_local_repair(
    *,
    current_text: str,
    declared_failure_type: str,
    current_round: int,
) -> tuple[str, dict]:
    return _l4_apply_behavioral_robustness_source_blind_local_repair(
        current_text=current_text,
        declared_failure_type=declared_failure_type,
        current_round=current_round,
        robustness_repair_enabled=_behavioral_robustness_deterministic_repair_enabled(),
        source_mode=_behavioral_robustness_source_mode(),
    )



def _extract_json_object(text: str) -> dict:
    # Canonical implementation moved to llm_response.extract_json_object.
    # This re-export preserves the existing internal call sites and test imports.
    from .llm_response import extract_json_object  # noqa: F811
    return extract_json_object(text, strict=False)



def _extract_response_text_openai(payload: dict) -> str:
    # Re-export kept for backward compatibility with existing callers.
    from .llm_provider_adapter import OpenAIProviderAdapter
    return OpenAIProviderAdapter._extract_response_text(payload)



def _parse_repair_actions(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                return [str(x) for x in payload if isinstance(x, str)]
        except Exception:
            pass
    return [x.strip() for x in text.split("|") if x.strip()]


def _apply_parse_error_pre_repair(model_text: str, output: str, failure_type: str) -> tuple[str, dict]:
    return _rule_engine_apply_parse_error_pre_repair(model_text, output, failure_type)


def _normalize_terminal_errors(executor_status: str, error_message: str, compile_error: str, simulate_error: str) -> tuple[str, str, str]:
    if str(executor_status or "").upper() == "PASS":
        return "", "", ""
    return str(error_message or ""), str(compile_error or ""), str(simulate_error or "")


def _parse_main_args() -> argparse.Namespace:
    """Parse CLI arguments for the live executor.

    Extracted from ``main()`` so the argument schema can be read and tested
    without running the full executor loop.
    """
    parser = argparse.ArgumentParser(
        description="Live Modelica executor with provider-configurable patching loop and OMC validation"
    )
    parser.add_argument("--task-id", default="")
    parser.add_argument("--failure-type", default="unknown")
    parser.add_argument("--expected-stage", default="unknown")
    parser.add_argument("--workflow-goal", default="")
    parser.add_argument("--source-model-path", default="")
    parser.add_argument("--mutated-model-path", default="")
    parser.add_argument("--source-library-path", default="")
    parser.add_argument("--source-package-name", default="")
    parser.add_argument("--source-library-model-path", default="")
    parser.add_argument("--source-qualified-model-name", default="")
    parser.add_argument("--repair-actions", default="")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--simulate-stop-time", type=float, default=0.2)
    parser.add_argument("--simulate-intervals", type=int, default=20)
    parser.add_argument("--backend", choices=["auto", "omc", "openmodelica_docker"], default="auto")
    parser.add_argument("--docker-image", default=os.getenv("GATEFORGE_OM_IMAGE", DEFAULT_DOCKER_IMAGE))
    parser.add_argument("--planner-backend", choices=["auto", "gemini", "openai", "rule"], default="auto")
    parser.add_argument("--transparent-repair-loop", choices=["on", "off"], default="on")
    parser.add_argument("--remedy-pack-enabled", choices=["on", "off"], default="on")
    parser.add_argument("--capability-intervention-pack-enabled", choices=["on", "off"], default="off")
    parser.add_argument("--broader-change-pack-enabled", choices=["on", "off"], default="off")
    parser.add_argument("--experience-replay", choices=["on", "off"], default="off")
    parser.add_argument("--experience-source", default="")
    parser.add_argument("--planner-experience-injection", choices=["on", "off"], default="off")
    parser.add_argument("--planner-experience-max-tokens", type=int, default=400)
    parser.add_argument("--extra-model-load", action="append", default=[], dest="extra_model_loads",
                        help="Extra Modelica package to loadModel() before the repair file (repeatable). "
                             "E.g. --extra-model-load AixLib for AixLib-based models.")
    parser.add_argument("--out", default="")
    return parser.parse_args()


def _summarize_executor_runtime_hygiene(*, attempts: list[dict]) -> dict:
    """Summarize runtime safety and prompt-hygiene evidence from attempt rows."""
    planner_event_count = 0
    repair_safety_event_count = 0
    repair_safety_blocked_count = 0
    candidate_text_checkpoint_count = 0
    rollback_evaluated_count = 0
    rollback_applied_count = 0
    planner_experience_context_truncated_count = 0
    replan_context_truncated_count = 0
    for row in attempts:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("planner_event"), dict):
            planner_event_count += 1
        repair_safety_events = row.get("repair_safety_events")
        if isinstance(repair_safety_events, list):
            repair_safety_event_count += len(repair_safety_events)
        if bool(row.get("repair_safety_blocked")):
            repair_safety_blocked_count += 1
        if isinstance(row.get("candidate_text_checkpoint"), dict):
            candidate_text_checkpoint_count += 1
        if bool(row.get("rollback_evaluated")):
            rollback_evaluated_count += 1
        if bool(row.get("rollback_applied")):
            rollback_applied_count += 1
        planner_injection = row.get("planner_experience_injection")
        context_truncation = (
            planner_injection.get("context_truncation")
            if isinstance(planner_injection, dict)
            else None
        )
        if isinstance(context_truncation, dict) and bool(context_truncation.get("was_truncated")):
            planner_experience_context_truncated_count += 1
        replan_caps = row.get("replan_context_prompt_caps")
        if isinstance(replan_caps, dict) and bool(replan_caps.get("was_truncated")):
            replan_context_truncated_count += 1
    return {
        "planner_event_count": int(planner_event_count),
        "repair_safety_event_count": int(repair_safety_event_count),
        "repair_safety_blocked_count": int(repair_safety_blocked_count),
        "candidate_text_checkpoint_count": int(candidate_text_checkpoint_count),
        "rollback_evaluated_count": int(rollback_evaluated_count),
        "rollback_applied_count": int(rollback_applied_count),
        "planner_experience_context_truncated_count": int(planner_experience_context_truncated_count),
        "replan_context_truncated_count": int(replan_context_truncated_count),
        "context_hygiene_truncation_seen": bool(
            planner_experience_context_truncated_count > 0
            or replan_context_truncated_count > 0
        ),
    }


def _summarize_product_gap_sidecar(*, attempts: list[dict]) -> dict:
    prompt_token_total = 0
    workflow_goal_reanchoring_observed = False
    full_omc_error_propagation_observed = False
    latest_dynamic_audit = {
        "static_prefix_stable": False,
        "dynamic_timestamp_found": False,
        "dynamic_task_id_found": False,
        "absolute_path_found": False,
    }
    for row in attempts:
        if not isinstance(row, dict):
            continue
        prompt_token_total += int(row.get("prompt_token_estimate") or 0)
        workflow_goal_reanchoring_observed = workflow_goal_reanchoring_observed or bool(
            row.get("workflow_goal_reanchoring_observed")
        )
        full_omc_error_propagation_observed = full_omc_error_propagation_observed or bool(
            row.get("full_omc_error_propagation_observed")
        )
        dynamic_audit = row.get("dynamic_system_prompt_field_audit_result")
        if isinstance(dynamic_audit, dict) and dynamic_audit:
            latest_dynamic_audit = dict(dynamic_audit)
    return {
        "scaffold_version": PRODUCT_GAP_SCAFFOLD_VERSION,
        "protocol_contract_version": PRODUCT_GAP_PROTOCOL_CONTRACT_VERSION,
        "token_count": int(prompt_token_total),
        "context_contract_version": PRODUCT_GAP_CONTEXT_CONTRACT_VERSION,
        "anti_reward_hacking_checklist_version": PRODUCT_GAP_ANTI_REWARD_HACKING_CHECKLIST_VERSION,
        "remedy_pack_enabled": bool(
            any(bool(row.get("remedy_pack_enabled")) for row in attempts if isinstance(row, dict))
        ),
        "capability_intervention_pack_enabled": bool(
            any(bool(row.get("capability_intervention_pack_enabled")) for row in attempts if isinstance(row, dict))
        ),
        "execution_strategy_upgrade_applied": bool(
            any(bool(row.get("execution_strategy_upgrade_applied")) for row in attempts if isinstance(row, dict))
        ),
        "replan_search_control_upgrade_applied": bool(
            any(bool(row.get("replan_search_control_upgrade_applied")) for row in attempts if isinstance(row, dict))
        ),
        "failure_diagnosis_upgrade_applied": bool(
            any(bool(row.get("failure_diagnosis_upgrade_applied")) for row in attempts if isinstance(row, dict))
        ),
        "broader_change_pack_enabled": bool(
            any(bool(row.get("broader_change_pack_enabled")) for row in attempts if isinstance(row, dict))
        ),
        "broader_execution_policy_restructuring_applied": bool(
            any(
                bool(row.get("broader_execution_policy_restructuring_applied"))
                for row in attempts
                if isinstance(row, dict)
            )
        ),
        "governed_model_upgrade_applied": bool(
            any(bool(row.get("governed_model_upgrade_applied")) for row in attempts if isinstance(row, dict))
        ),
        "workflow_goal_reanchoring_observed": bool(workflow_goal_reanchoring_observed),
        "dynamic_system_prompt_field_audit_result": latest_dynamic_audit,
        "full_omc_error_propagation_observed": bool(full_omc_error_propagation_observed),
    }


def _build_final_payload(
    *,
    args: argparse.Namespace,
    layout,
    started: float,
    current_text: str,
    source_model_text: str,
    attempts: list,
    multistep_memory: dict,
    final_check_ok: bool,
    final_simulate_ok: bool,
    final_error: str,
    final_compile_error: str,
    final_sim_error: str,
    final_stderr: str,
    executor_status: str,
    resolved_provider: str,
    backend: str,
    budget_cfg: dict,
    experience_replay_summary: dict | None = None,
    planner_experience_summary: dict | None = None,
) -> dict:
    """Assemble the final output payload from accumulated round-loop state.

    Derives all summary metrics, constructs the output JSON dict, and appends
    live-budget ledger data.  Returns the complete payload dict; does NOT write
    to disk or print (caller is responsible for I/O).
    """
    broader_change_pack_enabled = bool(str(args.broader_change_pack_enabled or "off") == "on")
    capability_intervention_pack_enabled = bool(
        str(args.capability_intervention_pack_enabled or "off") == "on"
    ) or broader_change_pack_enabled
    elapsed = round(time.monotonic() - started, 4)
    final_error, final_compile_error, final_sim_error = _normalize_terminal_errors(
        executor_status=executor_status,
        error_message=final_error,
        compile_error=final_compile_error,
        simulate_error=final_sim_error,
    )
    behavioral_eval = None
    if bool(final_check_ok and final_simulate_ok):
        behavioral_eval = _evaluate_behavioral_contract_from_model_text(
            current_text=current_text,
            source_model_text=source_model_text,
            failure_type=str(args.failure_type),
        )
        if behavioral_eval is None:
            behavioral_eval = _evaluate_semantic_time_constant_contract(
                current_text=current_text,
                source_model_text=source_model_text,
                failure_type=str(args.failure_type),
            )
    physics_contract_pass = bool(final_check_ok and final_simulate_ok)
    physics_contract_reasons: list[str] = []
    contract_fail_bucket = ""
    if isinstance(behavioral_eval, dict):
        physics_contract_pass = bool(behavioral_eval.get("pass"))
        physics_contract_reasons = [str(x) for x in (behavioral_eval.get("reasons") or []) if str(x).strip()]
        contract_fail_bucket = str(behavioral_eval.get("contract_fail_bucket") or "")
        scenario_results = [dict(item) for item in (behavioral_eval.get("scenario_results") or []) if isinstance(item, dict)]
        multi_step_stage = str(behavioral_eval.get("multi_step_stage") or "")
        multi_step_stage_2_unlocked = bool(behavioral_eval.get("multi_step_stage_2_unlocked"))
        multi_step_transition_seen = bool(behavioral_eval.get("multi_step_transition_seen"))
        multi_step_transition_reason = str(behavioral_eval.get("multi_step_transition_reason") or "")
    else:
        scenario_results = []
        multi_step_stage = ""
        multi_step_stage_2_unlocked = False
        multi_step_transition_seen = False
        multi_step_transition_reason = ""
    final_stage_context = _build_multistep_stage_context(
        failure_type=str(args.failure_type),
        behavioral_eval=behavioral_eval if isinstance(behavioral_eval, dict) else {},
        current_round=len(attempts),
        memory=multistep_memory,
    )
    local_search_audits = [
        row.get("source_blind_multistep_local_search")
        for row in attempts
        if isinstance(row, dict)
        and isinstance(row.get("source_blind_multistep_local_search"), dict)
        and bool((row.get("source_blind_multistep_local_search") or {}).get("applied"))
    ]
    local_search_kinds = [
        str((row or {}).get("search_kind") or "").strip()
        for row in local_search_audits
        if str((row or {}).get("search_kind") or "").strip()
    ]
    stage_1_unlock_via_local_search = bool(
        multi_step_stage_2_unlocked and any(kind == "stage_1_unlock" for kind in local_search_kinds)
    )
    stage_2_resolution_via_local_search = bool(
        physics_contract_pass and any(kind == "stage_2_resolution" for kind in local_search_kinds)
    )
    stage_1_unlock_via_adaptive_search = stage_1_unlock_via_local_search
    stage_2_resolution_via_adaptive_search = stage_2_resolution_via_local_search
    local_search_success_count = 1 if bool(physics_contract_pass and local_search_audits) else 0
    successful_directions = [
        str((row or {}).get("search_direction") or "").strip()
        for row in local_search_audits
        if str((row or {}).get("search_direction") or "").strip()
    ]
    adaptive_search_attempt_count = int(multistep_memory.get("adaptive_search_attempt_count") or len(local_search_audits) or 0)
    adaptive_search_success_count = 1 if bool(physics_contract_pass and local_search_audits) else 0
    search_improvement_seen = bool(stage_1_unlock_via_local_search or stage_2_resolution_via_local_search)
    cluster_only_resolution = bool(
        physics_contract_pass
        and not local_search_audits
        and any(
            bool(((row.get("source_blind_multistep_exposure_repair") or {}) if isinstance(row, dict) else {}).get("applied"))
            or bool(((row.get("source_blind_multistep_stage2_local_repair") or {}) if isinstance(row, dict) else {}).get("applied"))
            for row in attempts
            if isinstance(row, dict)
        )
    )
    template_only_resolution = cluster_only_resolution
    llm_markers = _extract_source_blind_multistep_markers(current_text)
    llm_request_count_delta_total = int(multistep_memory.get("llm_request_count_delta_total") or 0)
    llm_plan_used = bool(multistep_memory.get("llm_plan_used")) or llm_request_count_delta_total > 0
    llm_plan_generated = bool(multistep_memory.get("llm_plan_generated")) or llm_request_count_delta_total > 0
    llm_plan_parsed = bool(multistep_memory.get("llm_plan_parsed"))
    llm_plan_followed = bool(multistep_memory.get("llm_plan_followed"))
    llm_plan_branch_match = bool(multistep_memory.get("llm_plan_branch_match"))
    first_plan_branch_match = bool(multistep_memory.get("first_plan_branch_match"))
    first_plan_branch_miss = bool(llm_plan_generated and not first_plan_branch_match)
    replan_branch_match = bool(multistep_memory.get("replan_branch_match"))
    llm_plan_parameter_match = bool(multistep_memory.get("llm_plan_parameter_match"))
    llm_resolution_contributed = bool(multistep_memory.get("llm_resolution_contributed")) and bool(physics_contract_pass)
    llm_plan_helped_resolution = bool(multistep_memory.get("llm_plan_helped_resolution")) and bool(physics_contract_pass)
    llm_replan_used = bool(multistep_memory.get("llm_replan_used"))
    llm_replan_reason = str(multistep_memory.get("llm_replan_reason") or "")
    llm_replan_count = int(multistep_memory.get("llm_replan_count") or 0)
    llm_second_replan_used = bool(multistep_memory.get("llm_second_replan_used"))
    llm_second_replan_reason = str(multistep_memory.get("llm_second_replan_reason") or "")
    replan_helped_resolution = bool(multistep_memory.get("replan_helped_resolution")) and bool(physics_contract_pass)
    llm_first_plan_resolved = bool(multistep_memory.get("llm_first_plan_resolved")) and bool(physics_contract_pass)
    llm_replan_resolved = bool(multistep_memory.get("llm_replan_resolved")) and bool(physics_contract_pass)
    previous_branch_value = str(multistep_memory.get("previous_branch") or "").strip()
    new_branch_value = str(multistep_memory.get("new_branch") or "").strip()
    inferred_switch_branch_resolution = bool(
        physics_contract_pass
        and llm_replan_used
        and bool(multistep_memory.get("replan_switch_branch"))
        and (
            bool(multistep_memory.get("replan_branch_correction_used"))
            or (
                previous_branch_value
                and new_branch_value
                and previous_branch_value != new_branch_value
            )
        )
    )
    if inferred_switch_branch_resolution:
        replan_helped_resolution = True
        llm_replan_resolved = True
        multistep_memory["replan_helped_resolution"] = True
        multistep_memory["llm_replan_resolved"] = True
    wrong_branch_entered = bool(multistep_memory.get("trap_branch_entered"))
    wrong_branch_recovered = bool(wrong_branch_entered and multistep_memory.get("correct_branch_selected"))
    replan_branch_corrected = bool(llm_replan_used and wrong_branch_recovered)
    trap_escape_success = bool(multistep_memory.get("trap_branch_entered")) and bool(multistep_memory.get("correct_branch_selected"))
    llm_guided_search_used = bool(multistep_memory.get("llm_guided_search_used"))
    search_budget_from_llm_plan = int(multistep_memory.get("search_budget_from_llm_plan") or 0)
    search_budget_followed = bool(multistep_memory.get("search_budget_followed"))
    guided_search_closed_loop_observed = bool(multistep_memory.get("guided_search_closed_loop_observed"))
    llm_budget_helped_resolution = bool(multistep_memory.get("llm_budget_helped_resolution")) and bool(physics_contract_pass)
    inferred_guided_search_resolution = bool(
        physics_contract_pass
        and llm_guided_search_used
        and search_budget_followed
        and llm_plan_followed
    )
    if inferred_guided_search_resolution:
        llm_budget_helped_resolution = True
        multistep_memory["llm_budget_helped_resolution"] = True
        multistep_memory["llm_guided_search_resolution"] = True
    llm_guided_search_resolution = bool(inferred_guided_search_resolution or multistep_memory.get("llm_guided_search_resolution"))
    guided_search_bucket_sequence = [
        str(x).strip().lower()
        for x in (multistep_memory.get("guided_search_bucket_sequence") or [])
        if str(x).strip()
    ]
    guided_search_helped_branch_diagnosis = bool(
        llm_guided_search_used
        and search_budget_followed
        and "branch_diagnosis" in guided_search_bucket_sequence
        and (first_plan_branch_match or replan_branch_match or bool(multistep_memory.get("correct_branch_selected")))
    )
    guided_search_helped_trap_escape = bool(
        llm_guided_search_used
        and search_budget_followed
        and "branch_escape" in guided_search_bucket_sequence
        and (
            trap_escape_success
            or wrong_branch_recovered
            or int(multistep_memory.get("branch_escape_success_count") or 0) > 0
        )
    )
    guided_search_helped_replan = bool(
        llm_guided_search_used
        and search_budget_followed
        and bool(multistep_memory.get("guided_search_replan_after_observation"))
        and llm_replan_used
    )
    guided_search_helped_resolution = bool(llm_guided_search_resolution or llm_budget_helped_resolution)
    guided_search_was_decisive = bool(
        physics_contract_pass
        and guided_search_helped_resolution
        and not llm_first_plan_resolved
        and not llm_replan_resolved
    )
    resolution_primary_contribution = ""
    if physics_contract_pass:
        if guided_search_was_decisive:
            resolution_primary_contribution = "guided_search_decisive"
        elif llm_replan_resolved and bool(multistep_memory.get("replan_switch_branch")):
            resolution_primary_contribution = "switch_branch_replan"
        elif llm_replan_resolved:
            resolution_primary_contribution = "llm_replan"
        elif llm_first_plan_resolved:
            resolution_primary_contribution = "llm_first_plan"
        elif guided_search_helped_resolution:
            resolution_primary_contribution = "guided_search_assisted"
        elif (
            stage_2_resolution_via_local_search
            or stage_2_resolution_via_adaptive_search
            or cluster_only_resolution
            or template_only_resolution
            or local_search_success_count > 0
            or adaptive_search_success_count > 0
        ):
            resolution_primary_contribution = "deterministic"
    multistep_memory["first_plan_branch_miss"] = first_plan_branch_miss
    multistep_memory["replan_branch_corrected"] = replan_branch_corrected
    multistep_memory["guided_search_helped_branch_diagnosis"] = guided_search_helped_branch_diagnosis
    multistep_memory["guided_search_helped_trap_escape"] = guided_search_helped_trap_escape
    multistep_memory["guided_search_helped_resolution"] = guided_search_helped_resolution
    multistep_memory["guided_search_helped_replan"] = guided_search_helped_replan
    multistep_memory["guided_search_was_decisive"] = guided_search_was_decisive
    multistep_memory["resolution_primary_contribution"] = resolution_primary_contribution
    llm_only_resolution = bool(
        llm_resolution_contributed
        and llm_plan_followed
        and not llm_replan_used
        and not stage_1_unlock_via_local_search
        and not stage_2_resolution_via_local_search
        and not cluster_only_resolution
    )
    llm_plan_was_decisive = bool(llm_plan_helped_resolution and llm_only_resolution)
    llm_called_only = bool(llm_request_count_delta_total > 0 and not llm_plan_helped_resolution)
    executor_runtime_hygiene = _summarize_executor_runtime_hygiene(attempts=attempts)
    product_gap_sidecar = _summarize_product_gap_sidecar(attempts=attempts)
    payload = {
        "task_id": str(args.task_id),
        "execution_source": "agent_modelica_live_executor_v1",
        "remedy_pack_enabled": bool(str(args.remedy_pack_enabled or "on") == "on"),
        "capability_intervention_pack_enabled": capability_intervention_pack_enabled,
        "broader_change_pack_enabled": broader_change_pack_enabled,
        "failure_type": str(args.failure_type),
        "realism_version": str(llm_markers.get("realism_version") or ""),
        "llm_forcing": bool(llm_markers.get("llm_forcing")),
        "llm_forcing_profile": str(llm_markers.get("llm_profile") or ""),
        "executor_status": executor_status,
        "planner_backend": str(args.planner_backend),
        "experience_replay": dict(experience_replay_summary or {}),
        "planner_experience_injection": dict(planner_experience_summary or {}),
        "resolved_llm_provider": resolved_provider,
        "backend_used": backend,
        "uses_external_library": bool(layout.uses_external_library) if layout is not None else False,
        "check_model_pass": bool(final_check_ok),
        "simulate_pass": bool(final_simulate_ok),
        "physics_contract_pass": bool(physics_contract_pass),
        "physics_contract_reasons": physics_contract_reasons,
        "contract_pass": bool(physics_contract_pass),
        "contract_fail_bucket": contract_fail_bucket,
        "scenario_results": scenario_results,
        "multi_step_stage": multi_step_stage,
        "multi_step_stage_2_unlocked": multi_step_stage_2_unlocked,
        "multi_step_transition_seen": multi_step_transition_seen,
        "multi_step_transition_round": int(max(1, len(attempts))) if multi_step_transition_seen else 0,
        "multi_step_transition_reason": multi_step_transition_reason,
        "current_stage": str(final_stage_context.get("current_stage") or ""),
        "stage_2_unlocked": bool(final_stage_context.get("stage_2_unlocked")),
        "transition_round": int(final_stage_context.get("transition_round") or 0),
        "transition_reason": str(final_stage_context.get("transition_reason") or ""),
        "current_fail_bucket": str(final_stage_context.get("current_fail_bucket") or ""),
        "next_focus": str(final_stage_context.get("next_focus") or ""),
        "stage_1_unlock_cluster": str(multistep_memory.get("stage_1_unlock_cluster") or ""),
        "stage_2_first_fail_bucket": str(multistep_memory.get("stage_2_first_fail_bucket") or ""),
        "stage_2_branch": str(final_stage_context.get("stage_2_branch") or multistep_memory.get("stage_2_branch") or ""),
        "preferred_stage_2_branch": str(final_stage_context.get("preferred_stage_2_branch") or multistep_memory.get("preferred_stage_2_branch") or ""),
        "branch_mode": str(final_stage_context.get("branch_mode") or ""),
        "branch_reason": str(final_stage_context.get("branch_reason") or multistep_memory.get("branch_reason") or ""),
        "trap_branch": bool(final_stage_context.get("trap_branch")) if str(final_stage_context.get("stage_2_branch") or "").strip() else bool(multistep_memory.get("trap_branch_active")),
        "trap_branch_entered": bool(multistep_memory.get("trap_branch_entered")),
        "wrong_branch_entered": wrong_branch_entered,
        "correct_branch_selected": bool(final_stage_context.get("correct_branch_selected")) if str(final_stage_context.get("stage_2_branch") or "").strip() else bool(multistep_memory.get("correct_branch_selected")),
        "correct_branch_round": int(multistep_memory.get("correct_branch_round") or 0),
        "wrong_branch_recovered": wrong_branch_recovered,
        "stage_aware_control_applied": bool(multistep_memory.get("stage_aware_focus_applied")),
        "stage_1_revisit_after_unlock": bool(multistep_memory.get("stage_1_revisit_after_unlock")),
        "plan_stage": str(multistep_memory.get("last_plan_stage") or ""),
        "branch_stage": str(multistep_memory.get("last_plan_stage") or "") if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else "",
        "current_branch": str(final_stage_context.get("stage_2_branch") or multistep_memory.get("stage_2_branch") or ""),
        "preferred_branch": str(final_stage_context.get("preferred_stage_2_branch") or multistep_memory.get("preferred_stage_2_branch") or ""),
        "plan_goal": str(multistep_memory.get("last_plan_goal") or ""),
        "plan_actions": [str(x) for x in (multistep_memory.get("last_plan_actions") or []) if isinstance(x, str)],
        "plan_constraints": [str(x) for x in (multistep_memory.get("last_plan_constraints") or []) if isinstance(x, str)],
        "plan_stop_condition": str(multistep_memory.get("last_plan_stop_condition") or ""),
        "branch_plan_goal": str(multistep_memory.get("last_plan_goal") or "") if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else "",
        "branch_plan_actions": [str(x) for x in (multistep_memory.get("last_plan_actions") or []) if isinstance(x, str)] if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else [],
        "branch_plan_stop_condition": str(multistep_memory.get("last_plan_stop_condition") or "") if str(multistep_memory.get("last_plan_stage") or "").strip().lower() == "stage_2" else "",
        "stage_plan_generated": bool(multistep_memory.get("stage_plan_generated")),
        "stage_plan_followed": bool(multistep_memory.get("stage_plan_followed")),
        "executed_plan_stage": str(multistep_memory.get("executed_plan_stage") or ""),
        "executed_plan_action": str(multistep_memory.get("executed_plan_action") or ""),
        "plan_followed": bool(multistep_memory.get("stage_plan_followed")),
        "plan_conflict_rejected": bool(multistep_memory.get("plan_conflict_rejected")),
        "plan_conflict_rejected_count": int(multistep_memory.get("plan_conflict_rejected_count") or 0),
        "last_successful_stage_action": str(multistep_memory.get("last_successful_stage_action") or ""),
        "tried_candidate_values": [str(x) for x in (multistep_memory.get("tried_candidate_values") or []) if str(x).strip()],
        "bad_directions": [str(x) for x in (multistep_memory.get("bad_directions") or []) if str(x).strip()],
        "successful_directions": successful_directions,
        "local_search_attempt_count": int(multistep_memory.get("local_search_attempt_count") or 0),
        "local_search_success_count": local_search_success_count,
        "local_search_kinds": local_search_kinds,
        "adaptive_search_attempt_count": adaptive_search_attempt_count,
        "adaptive_search_success_count": adaptive_search_success_count,
        "adaptive_search_success_pct": 100.0 if adaptive_search_success_count > 0 else 0.0,
        "search_improvement_seen": search_improvement_seen,
        "search_regression_seen": bool(multistep_memory.get("search_regression_seen")),
        "search_bad_direction_count": int(multistep_memory.get("search_bad_direction_count") or 0),
        "best_stage_2_fail_bucket_seen": str(multistep_memory.get("best_stage_2_fail_bucket_seen") or ""),
        "stage_2_best_progress_seen": bool(multistep_memory.get("stage_2_best_progress_seen")),
        "stage_1_unlock_via_local_search": stage_1_unlock_via_local_search,
        "stage_2_resolution_via_local_search": stage_2_resolution_via_local_search,
        "stage_1_unlock_via_adaptive_search": stage_1_unlock_via_local_search,
        "stage_2_resolution_via_adaptive_search": stage_2_resolution_via_local_search,
        "cluster_only_resolution": cluster_only_resolution,
        "template_only_resolution": cluster_only_resolution,
        "branch_history": [str(x) for x in (multistep_memory.get("branch_history") or []) if str(x).strip()],
        "trap_branch_history": [str(x) for x in (multistep_memory.get("trap_branch_history") or []) if str(x).strip()],
        "last_trap_escape_direction": str(multistep_memory.get("last_trap_escape_direction") or ""),
        "last_successful_branch_correction": str(multistep_memory.get("last_successful_branch_correction") or ""),
        "branch_bad_directions": [str(x) for x in (multistep_memory.get("branch_bad_directions") or []) if str(x).strip()],
        "branch_reentry_count": int(multistep_memory.get("branch_reentry_count") or 0),
        "repeated_trap_branch": bool(int(multistep_memory.get("branch_reentry_count") or 0) > 0),
        "branch_escape_attempt_count": int(multistep_memory.get("branch_escape_attempt_count") or 0),
        "branch_escape_success_count": int(multistep_memory.get("branch_escape_success_count") or 0),
        "branch_escape_success_pct": round((int(multistep_memory.get("branch_escape_success_count") or 0) / max(1, int(multistep_memory.get("branch_escape_attempt_count") or 0))) * 100.0, 2) if int(multistep_memory.get("branch_escape_attempt_count") or 0) > 0 else 0.0,
        "branch_budget_reallocated_count": int(multistep_memory.get("branch_budget_reallocated_count") or 0),
        "branch_escape_attempted": bool(int(multistep_memory.get("branch_escape_attempt_count") or 0) > 0),
        "branch_escape_succeeded": bool(int(multistep_memory.get("branch_escape_success_count") or 0) > 0),
        "branch_escape_direction": str(multistep_memory.get("last_trap_escape_direction") or ""),
        "branch_budget_reallocated": bool(int(multistep_memory.get("branch_budget_reallocated_count") or 0) > 0),
        "llm_plan_used": llm_plan_used,
        "llm_plan_reason": str(multistep_memory.get("llm_plan_reason") or ""),
        "llm_plan_generated": llm_plan_generated,
        "llm_plan_parsed": llm_plan_parsed,
        "llm_plan_followed": llm_plan_followed,
        "planner_contract_version": str(multistep_memory.get("planner_contract_version") or ""),
        "planner_family": str(multistep_memory.get("planner_family") or ""),
        "planner_adapter": str(multistep_memory.get("planner_adapter") or ""),
        "planner_request_kind": str(multistep_memory.get("planner_request_kind") or ""),
        "llm_plan_branch_match": llm_plan_branch_match,
        "first_plan_branch_match": first_plan_branch_match,
        "first_plan_branch_miss": first_plan_branch_miss,
        "replan_branch_match": replan_branch_match,
        "replan_branch_corrected": replan_branch_corrected,
        "llm_plan_parameter_match": llm_plan_parameter_match,
        "llm_plan_helped_resolution": llm_plan_helped_resolution,
        "llm_plan_was_decisive": llm_plan_was_decisive,
        "llm_called_only": llm_called_only,
        "llm_plan_failure_mode": str(multistep_memory.get("llm_plan_failure_mode") or ""),
        "llm_plan_diagnosed_stage": str(multistep_memory.get("llm_plan_diagnosed_stage") or ""),
        "llm_plan_diagnosed_branch": str(multistep_memory.get("llm_plan_diagnosed_branch") or ""),
        "llm_plan_preferred_branch": str(multistep_memory.get("llm_plan_preferred_branch") or ""),
        "llm_plan_repair_goal": str(multistep_memory.get("llm_plan_repair_goal") or ""),
        "llm_plan_candidate_parameters": [
            str(x) for x in (multistep_memory.get("llm_plan_candidate_parameters") or []) if str(x).strip()
        ],
        "llm_plan_candidate_value_directions": [
            str(x) for x in (multistep_memory.get("llm_plan_candidate_value_directions") or []) if str(x).strip()
        ],
        "llm_plan_why_not_other_branch": str(multistep_memory.get("llm_plan_why_not_other_branch") or ""),
        "llm_plan_stop_condition": str(multistep_memory.get("llm_plan_stop_condition") or ""),
        "llm_replan_used": llm_replan_used,
        "llm_replan_reason": llm_replan_reason,
        "llm_replan_count": llm_replan_count,
        "llm_second_replan_used": llm_second_replan_used,
        "llm_second_replan_reason": llm_second_replan_reason,
        "previous_plan_failed_signal": str(multistep_memory.get("previous_plan_failed_signal") or ""),
        "previous_branch": str(multistep_memory.get("previous_branch") or ""),
        "new_branch": str(multistep_memory.get("new_branch") or ""),
        "replan_goal": str(multistep_memory.get("replan_goal") or ""),
        "replan_candidate_parameters": [
            str(x) for x in (multistep_memory.get("replan_candidate_parameters") or []) if str(x).strip()
        ],
        "replan_stop_condition": str(multistep_memory.get("replan_stop_condition") or ""),
        "branch_choice_reason": str(multistep_memory.get("branch_choice_reason") or ""),
        "replan_budget_total": int(multistep_memory.get("replan_budget_total") or 0),
        "replan_budget_for_branch_diagnosis": int(multistep_memory.get("replan_budget_for_branch_diagnosis") or 0),
        "replan_budget_for_branch_escape": int(multistep_memory.get("replan_budget_for_branch_escape") or 0),
        "replan_budget_for_resolution": int(multistep_memory.get("replan_budget_for_resolution") or 0),
        "replan_budget_consumed": int(multistep_memory.get("replan_budget_consumed") or 0),
        "replan_continue_current_branch": bool(multistep_memory.get("replan_continue_current_branch")),
        "replan_switch_branch": bool(multistep_memory.get("replan_switch_branch")),
        "replan_history": list(multistep_memory.get("replan_history") or []),
        "replan_branch_history": [str(x) for x in (multistep_memory.get("replan_branch_history") or []) if str(x).strip()],
        "replan_failed_directions": [str(x) for x in (multistep_memory.get("replan_failed_directions") or []) if str(x).strip()],
        "replan_successful_directions": [str(x) for x in (multistep_memory.get("replan_successful_directions") or []) if str(x).strip()],
        "replan_same_branch_stall_count": int(multistep_memory.get("replan_same_branch_stall_count") or 0),
        "replan_switch_branch_count": int(multistep_memory.get("replan_switch_branch_count") or 0),
        "replan_abandoned_branches": [str(x) for x in (multistep_memory.get("replan_abandoned_branches") or []) if str(x).strip()],
        "backtracking_used": bool(multistep_memory.get("backtracking_used")),
        "backtracking_reason": str(multistep_memory.get("backtracking_reason") or ""),
        "budget_reallocated_after_replan": bool(multistep_memory.get("budget_reallocated_after_replan")),
        "abandoned_plan_directions": [
            str(x) for x in (multistep_memory.get("abandoned_plan_directions") or []) if str(x).strip()
        ],
        "replan_branch_correction_used": bool(multistep_memory.get("replan_branch_correction_used")),
        "replan_helped_resolution": replan_helped_resolution,
        "llm_first_plan_resolved": llm_first_plan_resolved,
        "llm_replan_resolved": llm_replan_resolved,
        "trap_escape_success": trap_escape_success,
        "llm_guided_search_used": llm_guided_search_used,
        "search_budget_from_llm_plan": search_budget_from_llm_plan,
        "search_budget_followed": search_budget_followed,
        "guided_search_bucket_sequence": [str(x) for x in (multistep_memory.get("guided_search_bucket_sequence") or []) if str(x).strip()],
        "guided_search_order": str(multistep_memory.get("guided_search_order") or ""),
        "budget_bucket_consumed": dict(multistep_memory.get("budget_bucket_consumed") or {}),
        "budget_bucket_exhausted": [str(x) for x in (multistep_memory.get("budget_bucket_exhausted") or []) if str(x).strip()],
        "candidate_suppressed_by_budget": int(multistep_memory.get("candidate_suppressed_by_budget") or 0),
        "candidate_attempt_count_by_bucket": dict(multistep_memory.get("last_candidate_attempt_count_by_bucket") or {}),
        "resolution_skipped_due_to_budget": bool(multistep_memory.get("resolution_skipped_due_to_budget")),
        "branch_escape_skipped_due_to_budget": bool(multistep_memory.get("branch_escape_skipped_due_to_budget")),
        "branch_frozen_by_budget": [str(x) for x in (multistep_memory.get("branch_frozen_by_budget") or []) if str(x).strip()],
        "guided_search_observation_payload": dict(multistep_memory.get("guided_search_observation_payload") or {}),
        "guided_search_replan_after_observation": bool(multistep_memory.get("guided_search_replan_after_observation")),
        "guided_search_closed_loop_observed": guided_search_closed_loop_observed,
        "guided_search_helped_branch_diagnosis": guided_search_helped_branch_diagnosis,
        "guided_search_helped_trap_escape": guided_search_helped_trap_escape,
        "guided_search_helped_resolution": guided_search_helped_resolution,
        "guided_search_helped_replan": guided_search_helped_replan,
        "guided_search_was_decisive": guided_search_was_decisive,
        "llm_budget_helped_resolution": llm_budget_helped_resolution,
        "llm_guided_search_resolution": llm_guided_search_resolution,
        "resolution_primary_contribution": resolution_primary_contribution,
        "llm_request_count_delta": llm_request_count_delta_total,
        "llm_branch_correction_used": bool(multistep_memory.get("llm_branch_correction_used")),
        "llm_resolution_contributed": llm_resolution_contributed,
        "llm_only_resolution": llm_only_resolution,
        "regression_pass": bool(final_check_ok and final_simulate_ok),
        "rounds_used": int(len(attempts)),
        "elapsed_sec": elapsed,
        "executor_runtime_hygiene": executor_runtime_hygiene,
        "product_gap_sidecar": product_gap_sidecar,
        "error_message": final_error,
        "compile_error": final_compile_error,
        "simulate_error_message": final_sim_error,
        "stderr_snippet": final_stderr,
        "attempts": attempts,
        "live_budget": {
            "max_requests_per_run": int(budget_cfg.get("max_requests_per_run") or 0),
            "max_consecutive_429": int(budget_cfg.get("max_consecutive_429") or 0),
            "base_backoff_sec": float(budget_cfg.get("base_backoff_sec") or 0.0),
            "max_backoff_sec": float(budget_cfg.get("max_backoff_sec") or 0.0),
        },
    }
    ledger = _load_live_ledger(budget_cfg)
    payload["live_request_count"] = int(ledger.get("request_count") or 0)
    payload["rate_limit_429_count"] = int(ledger.get("rate_limit_429_count") or 0)
    payload["budget_stop_triggered"] = bool(ledger.get("budget_stop_triggered"))
    payload["live_budget_stop_reason"] = str(ledger.get("last_stop_reason") or "")
    quality_breakdown = _compute_repair_quality_breakdown(payload)
    experience_record = _build_experience_record(payload)
    payload["repair_quality_score"] = float(quality_breakdown.get("repair_quality_score") or 0.0)
    payload["repair_quality_breakdown"] = quality_breakdown
    payload["action_contributions"] = list(experience_record.get("action_contributions") or [])
    payload["resolution_attribution"] = dict(experience_record.get("resolution_attribution") or {})
    payload["resolution_path"] = str(experience_record.get("resolution_path") or "")
    payload["planner_invoked"] = bool(experience_record.get("planner_invoked"))
    payload["planner_used"] = bool(experience_record.get("planner_used"))
    payload["planner_decisive"] = bool(experience_record.get("planner_decisive"))
    payload["replay_used"] = bool(experience_record.get("replay_used"))
    payload["dominant_stage_subtype"] = str(experience_record.get("dominant_stage_subtype") or "")
    return payload


def main() -> None:
    args = _parse_main_args()

    started = time.monotonic()
    model_path = Path(str(args.mutated_model_path or "").strip() or str(args.source_model_path or "").strip())
    if not model_path.exists():
        payload = {
            "task_id": args.task_id,
            "failure_type": str(args.failure_type),
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": "model_path_missing",
            "compile_error": "model_path_missing",
            "simulate_error_message": "",
            "stderr_snippet": str(model_path),
            "attempts": [],
            "live_request_count": 0,
        }
        payload["repair_quality_breakdown"] = _compute_repair_quality_breakdown(payload)
        payload["repair_quality_score"] = float(payload["repair_quality_breakdown"].get("repair_quality_score") or 0.0)
        experience_record = _build_experience_record(payload)
        payload["action_contributions"] = list(experience_record.get("action_contributions") or [])
        payload["resolution_attribution"] = dict(experience_record.get("resolution_attribution") or {})
        payload["resolution_path"] = str(experience_record.get("resolution_path") or "")
        payload["planner_invoked"] = bool(experience_record.get("planner_invoked"))
        payload["planner_used"] = bool(experience_record.get("planner_used"))
        payload["planner_decisive"] = bool(experience_record.get("planner_decisive"))
        payload["replay_used"] = bool(experience_record.get("replay_used"))
        payload["dominant_stage_subtype"] = str(experience_record.get("dominant_stage_subtype") or "")
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return

    backend = str(args.backend).strip().lower()
    if backend == "auto":
        backend = "omc" if shutil.which("omc") else "openmodelica_docker"

    original_text = _read_text(model_path)
    source_model_text = ""
    source_model_path_raw = str(args.source_model_path or "").strip()
    if source_model_path_raw:
        source_model_path = Path(source_model_path_raw)
        if source_model_path.exists() and source_model_path.is_file():
            source_model_text = _read_text(source_model_path)
    model_name = _find_primary_model_name(original_text)
    if not model_name:
        payload = {
            "task_id": args.task_id,
            "failure_type": str(args.failure_type),
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": "model_name_not_found",
            "compile_error": "model_name_not_found",
            "simulate_error_message": "",
            "stderr_snippet": "",
            "attempts": [],
            "live_request_count": 0,
        }
        payload["repair_quality_breakdown"] = _compute_repair_quality_breakdown(payload)
        payload["repair_quality_score"] = float(payload["repair_quality_breakdown"].get("repair_quality_score") or 0.0)
        experience_record = _build_experience_record(payload)
        payload["action_contributions"] = list(experience_record.get("action_contributions") or [])
        payload["resolution_attribution"] = dict(experience_record.get("resolution_attribution") or {})
        payload["resolution_path"] = str(experience_record.get("resolution_path") or "")
        payload["planner_invoked"] = bool(experience_record.get("planner_invoked"))
        payload["planner_used"] = bool(experience_record.get("planner_used"))
        payload["planner_decisive"] = bool(experience_record.get("planner_decisive"))
        payload["replay_used"] = bool(experience_record.get("replay_used"))
        payload["dominant_stage_subtype"] = str(experience_record.get("dominant_stage_subtype") or "")
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return

    repair_actions = _parse_repair_actions(args.repair_actions)
    attempts: list[dict] = []
    current_text = original_text
    multistep_memory = make_multistep_memory()
    broader_change_pack_enabled = bool(str(args.broader_change_pack_enabled or "off") == "on")
    capability_intervention_pack_enabled = bool(
        str(args.capability_intervention_pack_enabled or "off") == "on"
    ) or broader_change_pack_enabled
    max_rounds = max(1, int(args.max_rounds))
    if broader_change_pack_enabled:
        # Broader-change execution policy restructuring is allowed to use a deeper search budget
        # while remaining on the same carried cases and executor shell.
        max_rounds = max(max_rounds, 2)
    final_check_ok = False
    final_simulate_ok = False
    final_error = ""
    final_compile_error = ""
    final_sim_error = ""
    final_stderr = ""
    executor_status = "FAILED"
    budget_cfg = _live_budget_config()
    try:
        resolved_provider = (
            "rule"
            if str(args.planner_backend) == "rule"
            else _resolve_llm_provider(str(args.planner_backend))[0]
        )
    except ValueError as exc:
        payload = {
            "task_id": args.task_id,
            "failure_type": str(args.failure_type),
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "elapsed_sec": round(time.monotonic() - started, 4),
            "error_message": str(exc),
            "compile_error": str(exc),
            "simulate_error_message": "",
            "stderr_snippet": "",
            "attempts": [],
            "live_request_count": 0,
        }
        payload["repair_quality_breakdown"] = _compute_repair_quality_breakdown(payload)
        payload["repair_quality_score"] = float(payload["repair_quality_breakdown"].get("repair_quality_score") or 0.0)
        experience_record = _build_experience_record(payload)
        payload["action_contributions"] = list(experience_record.get("action_contributions") or [])
        payload["resolution_attribution"] = dict(experience_record.get("resolution_attribution") or {})
        payload["resolution_path"] = str(experience_record.get("resolution_path") or "")
        payload["planner_invoked"] = bool(experience_record.get("planner_invoked"))
        payload["planner_used"] = bool(experience_record.get("planner_used"))
        payload["planner_decisive"] = bool(experience_record.get("planner_decisive"))
        payload["replay_used"] = bool(experience_record.get("replay_used"))
        payload["dominant_stage_subtype"] = str(experience_record.get("dominant_stage_subtype") or "")
        if str(args.out).strip():
            Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload))
        return
    rule_registry = _build_default_rule_registry()
    default_rule_order = [str(rule.rule_id or "") for rule in rule_registry.rules]
    experience_payload = {}
    if (
        str(args.experience_replay) == "on"
        or str(args.planner_experience_injection) == "on"
    ) and str(args.experience_source or "").strip():
        experience_payload = _load_json(Path(str(args.experience_source)))
    if isinstance(experience_payload, dict) and experience_payload:
        experience_coverage = _summarize_signal_coverage(experience_payload)
    else:
        experience_coverage = {
            "signal_coverage_status": "no_experience_source",
            "replay_eligible_action_count": 0,
            "replay_eligible_trigger_rate_pct": 0.0,
        }
    experience_replay_summary = {
        "enabled": bool(str(args.experience_replay) == "on"),
        "source": str(args.experience_source or ""),
        "used": False,
        "signal_coverage_status": str(experience_coverage.get("signal_coverage_status") or ""),
        "replay_eligible_action_count": int(experience_coverage.get("replay_eligible_action_count") or 0),
        "replay_eligible_trigger_rate_pct": float(experience_coverage.get("replay_eligible_trigger_rate_pct") or 0.0),
        "default_rule_order": list(default_rule_order),
        "reordered_rule_order": list(default_rule_order),
        "priority_reason": "experience_replay_disabled" if str(args.experience_replay) != "on" else "no_experience_source",
    }
    planner_experience_summary = {
        "enabled": bool(str(args.planner_experience_injection) == "on"),
        "source": str(args.experience_source or ""),
        "used": False,
        "positive_hint_count": 0,
        "caution_hint_count": 0,
        "prompt_token_estimate": 0,
        "max_context_tokens": int(args.planner_experience_max_tokens or 0),
        "truncated": False,
        "context_truncation": _default_context_truncation_summary(),
        "injection_reason": (
            "planner_experience_injection_disabled"
            if str(args.planner_experience_injection) != "on"
            else ("planner_experience_not_invoked" if isinstance(experience_payload, dict) and experience_payload else "no_experience_source")
        ),
    }
    checkpoint_manager = _CheckpointManager(max_retained=3)
    pending_rollback: dict | None = None

    def _planner_profile_name() -> str:
        return "planner_heavy" if resolved_provider in {"gemini", "openai"} else "default"

    def _capture_checkpoint_for_attempt(*, round_number: int, operation_name: str, attempt_row: dict) -> None:
        nonlocal pending_rollback
        checkpoint = checkpoint_manager.capture_if_needed(round_number, operation_name, current_text)
        if checkpoint is None:
            return
        scenario_results = attempt_row.get("scenario_results") if isinstance(attempt_row.get("scenario_results"), list) else []
        attempt_row["candidate_text_checkpoint"] = {
            **_checkpoint_summary(checkpoint),
            "operation_name": operation_name,
        }
        pending_rollback = {
            "round_number": int(round_number),
            "operation_name": str(operation_name),
            "pre_check_ok": bool(attempt_row.get("check_model_pass")),
            "pre_simulate_ok": (
                bool(attempt_row.get("simulate_pass")) if "simulate_pass" in attempt_row else None
            ),
            "pre_contract_pass": (
                bool(attempt_row.get("physics_contract_pass"))
                if "physics_contract_pass" in attempt_row
                else None
            ),
            "pre_scenario_pass_count": (
                _count_passed_scenarios(scenario_results)
                if "scenario_results" in attempt_row
                else None
            ),
        }

    def _apply_candidate_patch_to_current_text(
        *,
        round_number: int,
        operation_name: str,
        attempt_row: dict,
        patched_text: str,
    ) -> bool:
        nonlocal current_text
        try:
            spec = _get_operation(operation_name)
        except KeyError:
            spec = None
        profile = _planner_profile_name()
        if spec is not None:
            policy_summary = _operation_summary(spec, profile=profile)
            if bool(policy_summary.get("requires_safety_gate")):
                safety_result = _classify_repair_safety(
                    current_text,
                    patched_text,
                    profile=profile,
                )
                safety_event = {
                    "operation_name": operation_name,
                    "gate_required": True,
                    "verdict": str(safety_result.verdict),
                    "is_safe": bool(safety_result.is_safe),
                    "violation_ids": list(safety_result.violation_ids),
                    "violations": [
                        {
                            "pattern_id": str(v.pattern_id),
                            "description": str(v.description),
                            "verdict": str(v.verdict),
                            "detail": str(v.detail),
                        }
                        for v in safety_result.violations
                    ],
                    "profile": str(safety_result.profile),
                    "original_line_count": int(safety_result.original_line_count),
                    "proposed_line_count": int(safety_result.proposed_line_count),
                    "original_char_count": int(safety_result.original_char_count),
                    "proposed_char_count": int(safety_result.proposed_char_count),
                }
                existing_events = attempt_row.get("repair_safety_events")
                if not isinstance(existing_events, list):
                    existing_events = []
                existing_events.append(safety_event)
                attempt_row["repair_safety_events"] = existing_events
                attempt_row["repair_safety_last"] = dict(safety_event)
                if "repair_safety_blocked" not in attempt_row:
                    attempt_row["repair_safety_blocked"] = False
                if not safety_result.is_safe:
                    attempt_row["repair_safety_blocked"] = True
                    attempt_row["repair_safety_blocked_operation"] = str(operation_name)
                    attempt_row["repair_safety_blocked_verdict"] = str(safety_result.verdict)
                    attempt_row["repair_safety_blocked_violation_ids"] = list(safety_result.violation_ids)
                    return False
        _capture_checkpoint_for_attempt(
            round_number=round_number,
            operation_name=operation_name,
            attempt_row=attempt_row,
        )
        current_text = patched_text
        return True

    def _record_planner_event(*, attempt_row: dict, operation_name: str) -> None:
        try:
            spec = _get_operation(operation_name)
        except KeyError:
            return
        if not _is_planner_event(spec):
            return
        attempt_row["planner_event"] = _operation_summary(
            spec,
            profile=_planner_profile_name(),
        )

    def _run_transparent_repair_loop(*, workspace: Path, layout: _WorkspaceModelLayout) -> None:
        nonlocal current_text
        nonlocal final_check_ok
        nonlocal final_simulate_ok
        nonlocal final_error
        nonlocal final_compile_error
        nonlocal final_sim_error
        nonlocal final_stderr
        nonlocal executor_status
        nonlocal resolved_provider

        for round_idx in range(1, max_rounds + 1):
            layout.model_write_path.write_text(current_text, encoding="utf-8")
            rc, output, check_ok, simulate_ok = _run_check_and_simulate(
                workspace=workspace,
                model_load_files=layout.model_load_files,
                model_name=layout.model_identifier,
                timeout_sec=max(1, int(args.timeout_sec)),
                backend=backend,
                docker_image=str(args.docker_image),
                stop_time=float(args.simulate_stop_time),
                intervals=max(1, int(args.simulate_intervals)),
                extra_model_loads=list(args.extra_model_loads or []),
            )
            diagnostic = build_diagnostic_ir_v0(
                output=output,
                check_model_pass=bool(check_ok),
                simulate_pass=bool(simulate_ok),
                expected_stage=str(args.expected_stage or ""),
                declared_failure_type=str(args.failure_type or ""),
                declared_context_hints=_diagnostic_context_hints_from_model(
                    failure_type=str(args.failure_type or ""),
                    expected_stage=str(args.expected_stage or ""),
                    model_text=current_text,
                ),
            )
            observed_failure_type = str(diagnostic.get("error_type") or "none")
            reason = str(diagnostic.get("reason") or "")
            attempt_row = {
                "round": round_idx,
                "transparent_repair_loop": True,
                "return_code": rc,
                "check_model_pass": bool(check_ok),
                "simulate_pass": bool(simulate_ok),
                "observed_failure_type": observed_failure_type,
                "reason": reason,
                "diagnostic_ir": diagnostic,
                "log_excerpt": str(output or "")[:1200],
                "full_omc_error_output": str(output or ""),
            }
            attempts.append(attempt_row)

            behavioral_eval = None
            if check_ok and simulate_ok:
                behavioral_eval = _evaluate_behavioral_contract_from_model_text(
                    current_text=current_text,
                    source_model_text=source_model_text,
                    failure_type=str(args.failure_type),
                )
                if behavioral_eval is None:
                    behavioral_eval = _evaluate_semantic_time_constant_contract(
                        current_text=current_text,
                        source_model_text=source_model_text,
                        failure_type=str(args.failure_type),
                    )
                if isinstance(behavioral_eval, dict):
                    attempt_row["physics_contract_pass"] = bool(behavioral_eval.get("pass"))
                    attempt_row["physics_contract_reasons"] = [
                        str(x) for x in (behavioral_eval.get("reasons") or []) if str(x).strip()
                    ]
                    attempt_row["contract_pass"] = bool(behavioral_eval.get("pass"))
                    attempt_row["contract_fail_bucket"] = str(behavioral_eval.get("contract_fail_bucket") or "")
                    attempt_row["scenario_results"] = [
                        dict(item) for item in (behavioral_eval.get("scenario_results") or []) if isinstance(item, dict)
                    ]

            if check_ok and simulate_ok and (not isinstance(behavioral_eval, dict) or bool(behavioral_eval.get("pass"))):
                final_check_ok = True
                final_simulate_ok = True
                executor_status = "PASS"
                final_error = ""
                final_compile_error = ""
                final_sim_error = ""
                final_stderr = str(output or "")[-1200:]
                return

            if not check_ok:
                repair_failure_type = observed_failure_type if observed_failure_type != "none" else "model_check_error"
                final_error = reason or "compile_failed"
                final_compile_error = final_error
                final_sim_error = ""
                repair_feedback = str(output or "")
            elif check_ok and not simulate_ok:
                repair_failure_type = observed_failure_type if observed_failure_type != "none" else "simulate_error"
                final_error = reason or "simulate_failed"
                final_compile_error = ""
                final_sim_error = final_error
                repair_feedback = str(output or "")
            else:
                repair_failure_type = str(args.failure_type or "behavioral_contract_fail")
                final_error = str((behavioral_eval or {}).get("contract_fail_bucket") or "behavioral_contract_fail")
                final_compile_error = ""
                final_sim_error = final_error
                repair_feedback = json.dumps(
                    {
                        "contract_fail_bucket": str((behavioral_eval or {}).get("contract_fail_bucket") or ""),
                        "reasons": [str(x) for x in ((behavioral_eval or {}).get("reasons") or []) if str(x).strip()],
                        "scenario_results": [dict(item) for item in ((behavioral_eval or {}).get("scenario_results") or []) if isinstance(item, dict)],
                    },
                    ensure_ascii=False,
                )
            final_stderr = str(output or "")[-1200:]

            if round_idx >= max_rounds:
                return
            if str(args.planner_backend) == "rule":
                final_error = final_error or "rule_backend_no_patch_generation"
                return

            repair_action_candidates = [str(x) for x in repair_actions if str(x).strip()]
            if not repair_action_candidates:
                repair_action_candidates = (recommend_repair_actions_v0(
                    failure_type=str(repair_failure_type),
                    expected_stage=str(args.expected_stage),
                    diagnostic_payload=diagnostic,
                ).get("repair_actions") or [])
            patched_text, llm_err, resolved_provider = _llm_repair_model_text(
                planner_backend=str(args.planner_backend),
                original_text=current_text,
                failure_type=str(repair_failure_type),
                expected_stage=str(args.expected_stage),
                error_excerpt=str(repair_feedback or "")[:12000],
                repair_actions=[str(x) for x in repair_action_candidates[:4]],
                model_name=str(model_name or ""),
                workflow_goal=str(args.workflow_goal or ""),
                current_round=round_idx,
            )
            multistep_memory["llm_request_count_delta_total"] = int(
                multistep_memory.get("llm_request_count_delta_total") or 0
            ) + 1
            attempt_row["declaration_fix_repair"] = {
                "applied": isinstance(patched_text, str) and bool(patched_text.strip()),
                "err": str(llm_err or ""),
                "provider": str(resolved_provider or ""),
                "repair_failure_type": str(repair_failure_type),
            }
            if not isinstance(patched_text, str) or not patched_text.strip():
                final_error = str(llm_err or f"{resolved_provider}_patch_generation_failed")
                return
            guarded_patched, patch_guard = _guard_robustness_patch(
                original_text=current_text,
                patched_text=patched_text,
                failure_type=str(repair_failure_type),
            )
            attempt_row["patch_guard"] = patch_guard
            if not (isinstance(guarded_patched, str) and guarded_patched.strip()):
                final_error = str((patch_guard or {}).get("reason") or "patch_guard_rejected")
                return
            if not _apply_candidate_patch_to_current_text(
                round_number=round_idx,
                operation_name="apply_repair",
                attempt_row=attempt_row,
                patched_text=guarded_patched,
            ):
                final_error = str(attempt_row.get("repair_safety_blocked_verdict") or "repair_safety_blocked")
                return
            multistep_memory["llm_resolution_contributed"] = True

    with _temporary_workspace(prefix="gf_live_exec_") as td:
        workspace = Path(td)
        layout = _prepare_workspace_model_layout(
            workspace=workspace,
            fallback_model_path=model_path,
            primary_model_name=model_name,
            source_library_path=str(args.source_library_path or ""),
            source_package_name=str(args.source_package_name or ""),
            source_library_model_path=str(args.source_library_model_path or ""),
            source_qualified_model_name=str(args.source_qualified_model_name or ""),
        )
        if str(args.transparent_repair_loop or "on") != "on":
            raise ValueError("transparent_repair_loop_off_is_not_supported_in_v0_19_16")
        _run_transparent_repair_loop(workspace=workspace, layout=layout)

    payload = _build_final_payload(
        args=args,
        layout=layout,
        started=started,
        current_text=current_text,
        source_model_text=source_model_text,
        attempts=attempts,
        multistep_memory=multistep_memory,
        final_check_ok=final_check_ok,
        final_simulate_ok=final_simulate_ok,
        final_error=final_error,
        final_compile_error=final_compile_error,
        final_sim_error=final_sim_error,
        final_stderr=final_stderr,
        executor_status=executor_status,
        resolved_provider=resolved_provider,
        backend=backend,
        budget_cfg=budget_cfg,
        experience_replay_summary=experience_replay_summary,
        planner_experience_summary=planner_experience_summary,
    )
    if str(args.out).strip():
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
