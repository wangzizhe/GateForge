from __future__ import annotations

from .agent_modelica_v0_11_1_common import (
    ANTI_REWARD_HACKING_CHECKLIST_VERSION,
    CONTEXT_CONTRACT_VERSION,
    CURRENT_PROTOCOL_CONTRACT_VERSION,
    DEFAULT_V103_SUBSTRATE_BUILDER_PATH,
    SCHEMA_PREFIX as PREVIOUS_SCHEMA_PREFIX,
    SCAFFOLD_VERSION,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_8_0_common import REPO_ROOT


SCHEMA_PREFIX = "agent_modelica_v0_11_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_handoff_integrity_current"
DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_product_gap_substrate_builder_current"
DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_product_gap_substrate_admission_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current"

DEFAULT_V111_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_closeout_current" / "summary.json"

EXPECTED_V111_VERSION_DECISION = "v0_11_1_first_product_gap_patch_pack_ready"
EXPECTED_V111_HANDOFF_MODE = "freeze_first_product_gap_evaluation_substrate"
EXPECTED_V111_PATCH_PACK_STATUS = "ready"
EXPECTED_V111_VALIDATION_STATUS = "ready"

DEFAULT_PRODUCT_GAP_SUBSTRATE_KIND = "first_product_gap_evaluation_substrate"
DEFAULT_CARRIED_BASELINE_SOURCE = "v0_10_3_frozen_12_case_real_origin_substrate"
DEFAULT_PRODUCT_GAP_SUBSTRATE_SIZE = 12
PENDING_PROFILE_RUN = "pending_profile_run"

ALLOWED_DERIVATIVE_REASONS = {
    "protocol_scope_incompatibility",
    "shell_specific_observability_requirement",
    "instrumentation_only_transformation",
}

PATCH_PACK_OBSERVATION_FIELD_NAMES = [
    "workflow_goal_reanchoring_observed",
    "dynamic_system_prompt_field_audit_result",
    "full_omc_error_propagation_observed",
]


__all__ = [
    "ALLOWED_DERIVATIVE_REASONS",
    "ANTI_REWARD_HACKING_CHECKLIST_VERSION",
    "CONTEXT_CONTRACT_VERSION",
    "CURRENT_PROTOCOL_CONTRACT_VERSION",
    "DEFAULT_CARRIED_BASELINE_SOURCE",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PRODUCT_GAP_SUBSTRATE_ADMISSION_OUT_DIR",
    "DEFAULT_PRODUCT_GAP_SUBSTRATE_BUILDER_OUT_DIR",
    "DEFAULT_PRODUCT_GAP_SUBSTRATE_KIND",
    "DEFAULT_PRODUCT_GAP_SUBSTRATE_SIZE",
    "DEFAULT_V103_SUBSTRATE_BUILDER_PATH",
    "DEFAULT_V111_CLOSEOUT_PATH",
    "EXPECTED_V111_HANDOFF_MODE",
    "EXPECTED_V111_PATCH_PACK_STATUS",
    "EXPECTED_V111_VALIDATION_STATUS",
    "EXPECTED_V111_VERSION_DECISION",
    "PATCH_PACK_OBSERVATION_FIELD_NAMES",
    "PENDING_PROFILE_RUN",
    "PREVIOUS_SCHEMA_PREFIX",
    "SCHEMA_PREFIX",
    "SCAFFOLD_VERSION",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
