from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_14_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_RUNTIME_STACK_IDENTITY = "gateforge_live_executor_v1_with_current_openmodelica_runtime"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_broader_change_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_closeout_current"

DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"
DEFAULT_V133_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_3_closeout_current" / "summary.json"

EXPECTED_V133_VERSION_DECISION = "v0_13_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V133_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V133_CAVEAT = (
    "bounded_capability_interventions_side_evidence_only_and_stronger_bounded_escalation_not_in_scope_"
    "after_governed_same_source_evaluation"
)
EXPECTED_V133_NEXT_PRIMARY_QUESTION = "post_bounded_capability_intervention_broader_change_evaluation"

EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_SUBSTRATE_SIZE = 12
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
    "DEFAULT_V133_CLOSEOUT_PATH",
    "EXPECTED_V112_SUBSTRATE_SIZE",
    "EXPECTED_V112_VERSION_DECISION",
    "EXPECTED_V115_DOMINANT_GAP_FAMILY",
    "EXPECTED_V115_FORMAL_LABEL",
    "EXPECTED_V133_CAVEAT",
    "EXPECTED_V133_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V133_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V133_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
