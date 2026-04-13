from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_14_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_2_handoff_integrity_current"
DEFAULT_REMAINING_BROADER_CHANGE_SCOPE_ASSESSMENT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_2_remaining_broader_change_scope_assessment_current"
)
DEFAULT_STRONGER_BROADER_CHANGE_SCOPE_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_2_stronger_broader_change_scope_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_2_closeout_current"

DEFAULT_V141_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_closeout_current" / "summary.json"
DEFAULT_V140_GOVERNANCE_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_broader_change_governance_pack_current" / "summary.json"
)
DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"

EXPECTED_V141_VERSION_DECISIONS = frozenset(
    {
        "v0_14_1_first_broader_change_pack_side_evidence_only",
        "v0_14_1_first_broader_change_pack_non_material",
    }
)
EXPECTED_V141_EFFECT_CLASSES = frozenset({"side_evidence_only", "non_material"})
EXPECTED_V141_HANDOFF_MODE = "determine_whether_stronger_broader_change_is_in_scope"

EXPECTED_V140_ADMITTED_BROADER_CHANGE_IDS = frozenset(
    {
        "broader_L2_execution_policy_restructuring_v1",
        "governed_llm_backbone_upgrade_v1",
    }
)

EXPECTED_V115_FORMAL_LABEL = "product_gap_partial_but_interpretable"
CARRIED_DOMINANT_GAP_FAMILY = "residual_core_capability_gap"

ALLOWED_CANDIDATE_BROADER_CHANGE_SHAPES = frozenset(
    {
        "deeper_execution_policy_restructuring",
        "deeper_failure_diagnosis_restructuring",
        "stronger_governed_model_upgrade_variant",
        "mixed_governable_broader_change",
        "none",
    }
)

SCOPE_STATUS_NO_STRONGER = "no_stronger_broader_change_in_scope"
SCOPE_STATUS_STRONGER_IN_SCOPE = "stronger_broader_change_still_in_scope"
SCOPE_STATUS_INVALID = "scope_assessment_invalid"

STRONGER_BROADER_CHANGE_STATUS_JUSTIFIED = "justified"
STRONGER_BROADER_CHANGE_STATUS_NOT_IN_SCOPE = "not_in_scope"
STRONGER_BROADER_CHANGE_STATUS_INVALID = "invalid"

DEFAULT_NAMED_BLOCKER = (
    "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change"
)

DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE = {
    "task_base_widening_required": False,
    "same_source_comparison_break_required": False,
    "unconstrained_model_family_replacement_required": False,
    "per_candidate_ablation_required_before_next_step": False,
    "admitted_broader_change_set_already_exhausted": True,
}

__all__ = [
    "ALLOWED_CANDIDATE_BROADER_CHANGE_SHAPES",
    "CARRIED_DOMINANT_GAP_FAMILY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_NAMED_BLOCKER",
    "DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE",
    "DEFAULT_REMAINING_BROADER_CHANGE_SCOPE_ASSESSMENT_OUT_DIR",
    "DEFAULT_STRONGER_BROADER_CHANGE_SCOPE_SUMMARY_OUT_DIR",
    "DEFAULT_V115_CLOSEOUT_PATH",
    "DEFAULT_V140_GOVERNANCE_PACK_PATH",
    "DEFAULT_V141_CLOSEOUT_PATH",
    "EXPECTED_V115_FORMAL_LABEL",
    "EXPECTED_V140_ADMITTED_BROADER_CHANGE_IDS",
    "EXPECTED_V141_EFFECT_CLASSES",
    "EXPECTED_V141_HANDOFF_MODE",
    "EXPECTED_V141_VERSION_DECISIONS",
    "SCHEMA_PREFIX",
    "SCOPE_STATUS_INVALID",
    "SCOPE_STATUS_NO_STRONGER",
    "SCOPE_STATUS_STRONGER_IN_SCOPE",
    "STRONGER_BROADER_CHANGE_STATUS_INVALID",
    "STRONGER_BROADER_CHANGE_STATUS_JUSTIFIED",
    "STRONGER_BROADER_CHANGE_STATUS_NOT_IN_SCOPE",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
