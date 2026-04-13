from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_14_3"

DEFAULT_PHASE_LEDGER_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_3_phase_ledger_current"
DEFAULT_STOP_CONDITION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_3_stop_condition_current"
DEFAULT_MEANING_SYNTHESIS_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_3_meaning_synthesis_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_3_closeout_current"

DEFAULT_V140_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_closeout_current" / "summary.json"
DEFAULT_V141_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_closeout_current" / "summary.json"
DEFAULT_V142_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_2_closeout_current" / "summary.json"

EXPECTED_V140_VERSION_DECISION = "v0_14_0_broader_change_governance_ready"
EXPECTED_V141_VERSION_DECISIONS = frozenset(
    {
        "v0_14_1_first_broader_change_pack_non_material",
        "v0_14_1_first_broader_change_pack_side_evidence_only",
    }
)
EXPECTED_V142_VERSION_DECISION = "v0_14_2_stronger_broader_change_not_in_scope"

NEXT_PRIMARY_PHASE_QUESTION = "post_broader_change_exhaustion_even_broader_change_evaluation"

EXPLICIT_CAVEAT_LABEL = (
    "bounded_capability_interventions_and_governed_broader_changes_did_not_materially_rewrite_the_carried_"
    "product_gap_picture_and_stronger_governed_broader_escalation_is_not_in_scope"
)

__all__ = [
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_MEANING_SYNTHESIS_OUT_DIR",
    "DEFAULT_PHASE_LEDGER_OUT_DIR",
    "DEFAULT_STOP_CONDITION_OUT_DIR",
    "DEFAULT_V140_CLOSEOUT_PATH",
    "DEFAULT_V141_CLOSEOUT_PATH",
    "DEFAULT_V142_CLOSEOUT_PATH",
    "EXPECTED_V140_VERSION_DECISION",
    "EXPECTED_V141_VERSION_DECISIONS",
    "EXPECTED_V142_VERSION_DECISION",
    "EXPLICIT_CAVEAT_LABEL",
    "NEXT_PRIMARY_PHASE_QUESTION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
