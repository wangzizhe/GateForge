from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_12_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_PROTOCOL_CONTRACT_VERSION = "gateforge_live_executor_v1_contract"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_0_operational_remedy_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_0_closeout_current"

DEFAULT_V111_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_closeout_current" / "summary.json"
DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"
DEFAULT_V117_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_7_closeout_current" / "summary.json"

EXPECTED_V117_VERSION_DECISION = "v0_11_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V117_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V117_CAVEAT = "product_gap_remains_partial_rather_than_product_ready_after_governed_workflow_to_product_evaluation"
EXPECTED_V117_NEXT_PRIMARY_QUESTION = "workflow_to_product_gap_operational_remedy_evaluation"

EXPECTED_V111_VERSION_DECISION = "v0_11_1_first_product_gap_patch_pack_ready"
EXPECTED_V111_HANDOFF_MODE = "freeze_first_product_gap_evaluation_substrate"

EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_HANDOFF_MODE = "characterize_first_product_gap_profile"
EXPECTED_V112_SUBSTRATE_SIZE = 12

EXPECTED_V115_VERSION_DECISION = "v0_11_5_first_product_gap_profile_partial_but_interpretable"
EXPECTED_V115_ADJUDICATION_LABEL = "product_gap_partial_but_interpretable"
EXPECTED_V115_DOMINANT_GAP_FAMILY = "residual_core_capability_gap"

IN_SCOPE_REMEDY_FAMILIES = {
    "context_contract_hardening",
    "protocol_shell_hardening",
    "error_propagation_and_visibility_hardening",
}

DEFERRED_REMEDY_FAMILIES = {
    "anti_cheating_and_behavior_guardrail_hardening",
    "efficiency_observability_only",
}

EXPECTED_FIRST_PASS_REMEDY_IDS = {
    "workflow_goal_reanchoring_hardening",
    "dynamic_prompt_field_stability_hardening",
    "full_omc_error_visibility_hardening",
}


__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_PROTOCOL_CONTRACT_VERSION",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V111_CLOSEOUT_PATH",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V115_CLOSEOUT_PATH",
    "DEFAULT_V117_CLOSEOUT_PATH",
    "DEFERRED_REMEDY_FAMILIES",
    "EXPECTED_FIRST_PASS_REMEDY_IDS",
    "EXPECTED_V111_HANDOFF_MODE",
    "EXPECTED_V111_VERSION_DECISION",
    "EXPECTED_V112_HANDOFF_MODE",
    "EXPECTED_V112_SUBSTRATE_SIZE",
    "EXPECTED_V112_VERSION_DECISION",
    "EXPECTED_V115_ADJUDICATION_LABEL",
    "EXPECTED_V115_DOMINANT_GAP_FAMILY",
    "EXPECTED_V115_VERSION_DECISION",
    "EXPECTED_V117_CAVEAT",
    "EXPECTED_V117_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V117_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V117_VERSION_DECISION",
    "IN_SCOPE_REMEDY_FAMILIES",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
