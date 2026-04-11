from __future__ import annotations

from .agent_modelica_v0_11_0_common import (
    CURRENT_MAIN_EXECUTION_CHAIN,
    CURRENT_PROTOCOL_CONTRACT_VERSION,
    REPO_ROOT,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_PREFIX = "agent_modelica_v0_11_1"

CONTEXT_CONTRACT_VERSION = "v0_11_0_context_contract_v1"
ANTI_REWARD_HACKING_CHECKLIST_VERSION = "v0_11_0_anti_reward_hacking_checklist_v1"
SCAFFOLD_VERSION = "gateforge_live_executor_v1_scaffold"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_handoff_integrity_current"
DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_patch_pack_execution_current"
DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_bounded_validation_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_1_closeout_current"

DEFAULT_V110_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_0_closeout_current" / "summary.json"
DEFAULT_V110_GOVERNANCE_PACK_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_0_product_gap_governance_pack_current" / "summary.json"
DEFAULT_V103_SUBSTRATE_BUILDER_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_3_real_origin_substrate_builder_current" / "summary.json"

EXPECTED_V110_VERSION_DECISION = "v0_11_0_product_gap_governance_ready"
EXPECTED_V110_HANDOFF_MODE = "execute_first_product_gap_patch_pack"

VALIDATION_CASE_COUNT_MIN = 3


__all__ = [
    "ANTI_REWARD_HACKING_CHECKLIST_VERSION",
    "CONTEXT_CONTRACT_VERSION",
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_PROTOCOL_CONTRACT_VERSION",
    "DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR",
    "DEFAULT_V103_SUBSTRATE_BUILDER_PATH",
    "DEFAULT_V110_CLOSEOUT_PATH",
    "DEFAULT_V110_GOVERNANCE_PACK_PATH",
    "EXPECTED_V110_HANDOFF_MODE",
    "EXPECTED_V110_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "SCAFFOLD_VERSION",
    "VALIDATION_CASE_COUNT_MIN",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
