from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_12_3"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_3_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_3_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_3_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_3_closeout_current"

DEFAULT_V120_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_0_closeout_current" / "summary.json"
DEFAULT_V121_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_closeout_current" / "summary.json"
DEFAULT_V122_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_2_closeout_current" / "summary.json"

EXPECTED_V120_VERSION_DECISION = "v0_12_0_operational_remedy_governance_ready"
EXPECTED_V121_VERSION_DECISION = "v0_12_1_first_remedy_pack_non_material"
EXPECTED_V122_VERSION_DECISION = "v0_12_2_stronger_bounded_remedy_not_in_scope"

NEXT_PRIMARY_PHASE_QUESTION = "capability_level_improvement_evaluation_after_operational_remedy_exhaustion"

EXPLICIT_CAVEAT_LABEL = (
    "bounded_operational_remedies_non_material_and_stronger_remedies_not_in_scope_"
    "after_governed_same_source_evaluation"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V120_CLOSEOUT_PATH",
    "DEFAULT_V121_CLOSEOUT_PATH",
    "DEFAULT_V122_CLOSEOUT_PATH",
    "EXPECTED_V120_VERSION_DECISION",
    "EXPECTED_V121_VERSION_DECISION",
    "EXPECTED_V122_VERSION_DECISION",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
