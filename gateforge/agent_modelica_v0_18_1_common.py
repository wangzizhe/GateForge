from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_18_1"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_18_1_handoff_integrity_current"
DEFAULT_PHASE_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_18_1_phase_closeout_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_18_1_closeout_current"

DEFAULT_V180_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_18_0_closeout_current" / "summary.json"

EXPECTED_V180_VERSION_DECISION = "v0_18_0_no_honest_next_move_remains"
EXPECTED_V180_GOVERNANCE_STATUS = "governance_ready"
EXPECTED_V180_VIABILITY_STATUS = "not_justified"
EXPECTED_V180_GOVERNANCE_OUTCOME = "no_honest_next_move_remains"
EXPECTED_V180_HANDOFF_MODE = "prepare_v0_18_phase_closeout_or_stop"

PHASE_STOP_CONDITION_STATUS = "nearly_complete_with_explicit_caveat"
EXPLICIT_CAVEAT_LABEL = "no_honest_next_move_remains_after_explicit_post_transition_reassessment_of_the_carried_evidence_boundary"
NEXT_PRIMARY_PHASE_QUESTION = "post_v0_18_evidence_boundary_conclusion_or_stop"
REBUILD_PHASE_INPUTS_QUESTION = "rebuild_v0_18_1_phase_inputs_first"

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_PHASE_CLOSEOUT_OUT_DIR",
    "DEFAULT_V180_CLOSEOUT_PATH",
    "EXPECTED_V180_GOVERNANCE_OUTCOME",
    "EXPECTED_V180_GOVERNANCE_STATUS",
    "EXPECTED_V180_HANDOFF_MODE",
    "EXPECTED_V180_VERSION_DECISION",
    "EXPECTED_V180_VIABILITY_STATUS",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "PHASE_STOP_CONDITION_STATUS",
    "REBUILD_PHASE_INPUTS_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
