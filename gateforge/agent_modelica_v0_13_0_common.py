from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_13_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_RUNTIME_STACK_IDENTITY = "gateforge_live_executor_v1_with_current_openmodelica_runtime"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_capability_intervention_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_closeout_current"

DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"
DEFAULT_V123_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_3_closeout_current" / "summary.json"

EXPECTED_V123_VERSION_DECISION = "v0_12_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V123_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V123_CAVEAT = "bounded_operational_remedies_non_material_and_stronger_remedies_not_in_scope_after_governed_same_source_evaluation"
EXPECTED_V123_NEXT_PRIMARY_QUESTION = "capability_level_improvement_evaluation_after_operational_remedy_exhaustion"

EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_SUBSTRATE_SIZE = 12
EXPECTED_V115_VERSION_DECISION = "v0_11_5_first_product_gap_profile_partial_but_interpretable"
EXPECTED_V115_FORMAL_LABEL = "product_gap_partial_but_interpretable"
EXPECTED_V115_DOMINANT_GAP_FAMILY = "residual_core_capability_gap"


__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_RUNTIME_STACK_IDENTITY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V115_CLOSEOUT_PATH",
    "DEFAULT_V123_CLOSEOUT_PATH",
    "EXPECTED_V112_SUBSTRATE_SIZE",
    "EXPECTED_V112_VERSION_DECISION",
    "EXPECTED_V115_DOMINANT_GAP_FAMILY",
    "EXPECTED_V115_FORMAL_LABEL",
    "EXPECTED_V115_VERSION_DECISION",
    "EXPECTED_V123_CAVEAT",
    "EXPECTED_V123_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V123_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V123_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
