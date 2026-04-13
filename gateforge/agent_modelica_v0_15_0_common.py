from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_15_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_RUNTIME_STACK_IDENTITY = "gateforge_live_executor_v1_with_current_openmodelica_runtime"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_0_even_broader_change_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_0_closeout_current"

DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V143_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_3_closeout_current" / "summary.json"
DEFAULT_V141_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_closeout_current" / "summary.json"
DEFAULT_V142_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_2_closeout_current" / "summary.json"

EXPECTED_V143_VERSION_DECISION = "v0_14_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V143_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V143_CAVEAT = (
    "bounded_capability_interventions_and_governed_broader_changes_did_not_materially_rewrite_the_carried_"
    "product_gap_picture_and_stronger_governed_broader_escalation_is_not_in_scope"
)
EXPECTED_V143_NEXT_PRIMARY_QUESTION = "post_broader_change_exhaustion_even_broader_change_evaluation"

EXPECTED_V141_VERSION_DECISIONS = {
    "v0_14_1_first_broader_change_pack_non_material",
    "v0_14_1_first_broader_change_pack_side_evidence_only",
}
EXPECTED_V142_VERSION_DECISION = "v0_14_2_stronger_broader_change_not_in_scope"
EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_SUBSTRATE_SIZE = 12

__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_RUNTIME_STACK_IDENTITY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V141_CLOSEOUT_PATH",
    "DEFAULT_V142_CLOSEOUT_PATH",
    "DEFAULT_V143_CLOSEOUT_PATH",
    "EXPECTED_V112_SUBSTRATE_SIZE",
    "EXPECTED_V112_VERSION_DECISION",
    "EXPECTED_V141_VERSION_DECISIONS",
    "EXPECTED_V142_VERSION_DECISION",
    "EXPECTED_V143_CAVEAT",
    "EXPECTED_V143_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V143_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V143_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
