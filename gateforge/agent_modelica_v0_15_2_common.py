from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_15_2"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_2_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_2_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_2_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_2_closeout_current"

DEFAULT_V150_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_0_closeout_current" / "summary.json"
DEFAULT_V151_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_15_1_closeout_current" / "summary.json"

EXPECTED_V150_VERSION_DECISION = "v0_15_0_even_broader_change_governance_partial"
EXPECTED_V151_VERSION_DECISION = "v0_15_1_even_broader_execution_not_justified"

NEXT_PRIMARY_PHASE_QUESTION = "post_even_broader_change_viability_exhaustion_next_change_question"

EXPLICIT_CAVEAT_LABEL = (
    "even_broader_change_governance_was_frozen_but_execution_arc_viability_remained_not_justified_"
    "on_the_carried_same_source_baseline"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V150_CLOSEOUT_PATH",
    "DEFAULT_V151_CLOSEOUT_PATH",
    "EXPECTED_V150_VERSION_DECISION",
    "EXPECTED_V151_VERSION_DECISION",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
