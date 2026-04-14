from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_17_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_RUNTIME_STACK_IDENTITY = "gateforge_live_executor_v1_with_current_openmodelica_runtime"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_0_transition_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_0_closeout_current"

DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V160_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_0_closeout_current" / "summary.json"
DEFAULT_V161_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_1_closeout_current" / "summary.json"

EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_SUBSTRATE_SIZE = 12

EXPECTED_V160_VERSION_DECISION = "v0_16_0_no_honest_next_change_question_remains"
EXPECTED_V160_GOVERNANCE_OUTCOME = "no_honest_next_local_change_question_remains"

EXPECTED_V161_VERSION_DECISION = "v0_16_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V161_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V161_CAVEAT = (
    "no_honest_local_next_change_question_remains_on_the_carried_same_12_case_baseline_after_governed_"
    "post_v0_15_reassessment"
)
EXPECTED_V161_NEXT_PRIMARY_QUESTION = "carried_baseline_evidence_exhaustion_transition_evaluation"

__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_RUNTIME_STACK_IDENTITY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V160_CLOSEOUT_PATH",
    "DEFAULT_V161_CLOSEOUT_PATH",
    "EXPECTED_V112_SUBSTRATE_SIZE",
    "EXPECTED_V112_VERSION_DECISION",
    "EXPECTED_V160_GOVERNANCE_OUTCOME",
    "EXPECTED_V160_VERSION_DECISION",
    "EXPECTED_V161_CAVEAT",
    "EXPECTED_V161_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V161_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V161_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
