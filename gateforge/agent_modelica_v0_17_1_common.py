from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_17_1"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_1_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_1_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_1_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_1_closeout_current"

DEFAULT_V170_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_17_0_closeout_current" / "summary.json"

EXPECTED_V170_VERSION_DECISION = "v0_17_0_no_honest_transition_question_remains"
EXPECTED_V170_GOVERNANCE_OUTCOME = "no_honest_transition_question_remains"

NEXT_PRIMARY_PHASE_QUESTION = "post_transition_question_exhaustion_next_honest_move"

EXPLICIT_CAVEAT_LABEL = (
    "no_honest_governed_transition_question_remains_on_the_carried_same_12_case_baseline_after_explicit_"
    "evidence_exhaustion_reassessment"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V170_CLOSEOUT_PATH",
    "EXPECTED_V170_GOVERNANCE_OUTCOME",
    "EXPECTED_V170_VERSION_DECISION",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
