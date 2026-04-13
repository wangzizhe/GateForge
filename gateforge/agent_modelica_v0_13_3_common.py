from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_13_3"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_3_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_3_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_3_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_3_closeout_current"

DEFAULT_V130_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_closeout_current" / "summary.json"
DEFAULT_V131_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_closeout_current" / "summary.json"
DEFAULT_V132_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_2_closeout_current" / "summary.json"

EXPECTED_V130_VERSION_DECISION = "v0_13_0_capability_intervention_governance_ready"
EXPECTED_V131_VERSION_DECISION = "v0_13_1_first_capability_intervention_pack_side_evidence_only"
EXPECTED_V132_VERSION_DECISION = "v0_13_2_stronger_bounded_capability_intervention_not_in_scope"

NEXT_PRIMARY_PHASE_QUESTION = "post_bounded_capability_intervention_broader_change_evaluation"

EXPLICIT_CAVEAT_LABEL = (
    "bounded_capability_interventions_side_evidence_only_and_stronger_bounded_escalation_not_in_scope_"
    "after_governed_same_source_evaluation"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V130_CLOSEOUT_PATH",
    "DEFAULT_V131_CLOSEOUT_PATH",
    "DEFAULT_V132_CLOSEOUT_PATH",
    "EXPECTED_V130_VERSION_DECISION",
    "EXPECTED_V131_VERSION_DECISION",
    "EXPECTED_V132_VERSION_DECISION",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
