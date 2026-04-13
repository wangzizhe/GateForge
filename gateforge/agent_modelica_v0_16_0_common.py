from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_16_0"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
CURRENT_RUNTIME_STACK_IDENTITY = "gateforge_live_executor_v1_with_current_openmodelica_runtime"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_0_handoff_integrity_current"
DEFAULT_GOVERNANCE_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_0_next_change_question_governance_pack_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_0_closeout_current"

DEFAULT_V112_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_closeout_current" / "summary.json"
DEFAULT_V150_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_0_closeout_current" / "summary.json"
DEFAULT_V151_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_1_closeout_current" / "summary.json"
DEFAULT_V152_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_2_closeout_current" / "summary.json"

EXPECTED_V152_VERSION_DECISION = "v0_15_phase_nearly_complete_with_explicit_caveat"
EXPECTED_V152_PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_caveat"
EXPECTED_V152_CAVEAT = (
    "even_broader_change_governance_was_frozen_but_execution_arc_viability_remained_not_justified_on_the_"
    "carried_same_source_baseline"
)
EXPECTED_V152_NEXT_PRIMARY_QUESTION = "post_even_broader_change_viability_exhaustion_next_change_question"

EXPECTED_V150_VERSION_DECISION = "v0_15_0_even_broader_change_governance_partial"
EXPECTED_V151_VERSION_DECISION = "v0_15_1_even_broader_execution_not_justified"
EXPECTED_V151_NOT_JUSTIFIED_REASON = (
    "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change"
)
EXPECTED_V112_VERSION_DECISION = "v0_11_2_first_product_gap_substrate_ready"
EXPECTED_V112_SUBSTRATE_SIZE = 12

__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "CURRENT_RUNTIME_STACK_IDENTITY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_GOVERNANCE_PACK_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_V112_CLOSEOUT_PATH",
    "DEFAULT_V150_CLOSEOUT_PATH",
    "DEFAULT_V151_CLOSEOUT_PATH",
    "DEFAULT_V152_CLOSEOUT_PATH",
    "EXPECTED_V112_SUBSTRATE_SIZE",
    "EXPECTED_V112_VERSION_DECISION",
    "EXPECTED_V150_VERSION_DECISION",
    "EXPECTED_V151_NOT_JUSTIFIED_REASON",
    "EXPECTED_V151_VERSION_DECISION",
    "EXPECTED_V152_CAVEAT",
    "EXPECTED_V152_NEXT_PRIMARY_QUESTION",
    "EXPECTED_V152_PHASE_STOP_CONDITION_STATUS",
    "EXPECTED_V152_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
