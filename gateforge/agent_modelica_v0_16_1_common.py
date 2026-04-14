from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_16_1"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_1_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_1_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_1_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_1_closeout_current"

DEFAULT_V160_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_16_0_closeout_current" / "summary.json"

EXPECTED_V160_VERSION_DECISION = "v0_16_0_no_honest_next_change_question_remains"
EXPECTED_V160_GOVERNANCE_OUTCOME = "no_honest_next_local_change_question_remains"

NEXT_PRIMARY_PHASE_QUESTION = "carried_baseline_evidence_exhaustion_transition_evaluation"

EXPLICIT_CAVEAT_LABEL = (
    "no_honest_local_next_change_question_remains_on_the_carried_same_12_case_baseline_after_governed_"
    "post_v0_15_reassessment"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V160_CLOSEOUT_PATH",
    "EXPECTED_V160_GOVERNANCE_OUTCOME",
    "EXPECTED_V160_VERSION_DECISION",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
