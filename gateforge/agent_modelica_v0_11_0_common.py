from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_11_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_PROTOCOL_CONTRACT_VERSION = "gateforge_live_executor_v1_contract"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_0_product_gap_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_0_closeout_current"

DEFAULT_V103_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_closeout_current" / "summary.json"
DEFAULT_V104_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_4_closeout_current" / "summary.json"
DEFAULT_V106_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_closeout_current" / "summary.json"
DEFAULT_V108_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_8_closeout_current" / "summary.json"

EXPECTED_V108_VERSION_DECISION = "v0_10_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V108_PHASE_STATUS = "nearly_complete"
EXPECTED_V108_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V108_CAVEAT = "real_origin_workflow_readiness_remains_partial_rather_than_supported_even_after_real_origin_source_shift"
EXPECTED_V108_NEXT_PRIMARY_QUESTION = "workflow_to_product_gap_evaluation"

EXPECTED_V103_VERSION_DECISION = "v0_10_3_first_real_origin_workflow_substrate_ready"
EXPECTED_V103_SUBSTRATE_SIZE = 12

EXPECTED_V104_VERSION_DECISION = "v0_10_4_first_real_origin_workflow_profile_characterized"
EXPECTED_V104_PROFILE_RUN_COUNT_MIN = 3
EXPECTED_V104_UNCLASSIFIED_NON_SUCCESS_COUNT = 0

EXPECTED_V106_VERSION_DECISION = "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable"
EXPECTED_V106_ADJUDICATION_LABEL = "real_origin_workflow_readiness_partial_but_interpretable"
EXPECTED_V106_DOMINANT_NON_SUCCESS_LABEL_FAMILY = "extractive_conversion_chain_unresolved"

EXPECTED_PATCH_CANDIDATE_NAMES = {
    "workflow_goal_reanchoring_patch_candidate",
    "system_prompt_dynamic_field_audit_patch_candidate",
    "full_omc_error_propagation_audit_patch_candidate",
}


__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_PROTOCOL_CONTRACT_VERSION",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V103_CLOSEOUT_PATH",
    "DEFAULT_V104_CLOSEOUT_PATH",
    "DEFAULT_V106_CLOSEOUT_PATH",
    "DEFAULT_V108_CLOSEOUT_PATH",
    "EXPECTED_PATCH_CANDIDATE_NAMES",
    "EXPECTED_V103_SUBSTRATE_SIZE",
    "EXPECTED_V103_VERSION_DECISION",
    "EXPECTED_V104_PROFILE_RUN_COUNT_MIN",
    "EXPECTED_V104_UNCLASSIFIED_NON_SUCCESS_COUNT",
    "EXPECTED_V104_VERSION_DECISION",
    "EXPECTED_V106_ADJUDICATION_LABEL",
    "EXPECTED_V106_DOMINANT_NON_SUCCESS_LABEL_FAMILY",
    "EXPECTED_V106_VERSION_DECISION",
    "EXPECTED_V108_CAVEAT",
    "EXPECTED_V108_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V108_PHASE_STATUS",
    "EXPECTED_V108_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V108_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
