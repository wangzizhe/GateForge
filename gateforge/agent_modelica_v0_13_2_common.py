from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_13_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_2_handoff_integrity_current"
DEFAULT_REMAINING_CAPABILITY_INTERVENTION_SCOPE_ASSESSMENT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_2_remaining_capability_intervention_scope_assessment_current"
)
DEFAULT_STRONGER_CAPABILITY_INTERVENTION_SCOPE_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_2_stronger_capability_intervention_scope_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_2_closeout_current"

DEFAULT_V131_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_closeout_current" / "summary.json"
DEFAULT_V130_GOVERNANCE_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_capability_intervention_governance_pack_current" / "summary.json"
)
DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"

EXPECTED_V131_VERSION_DECISIONS = frozenset(
    {
        "v0_13_1_first_capability_intervention_pack_non_material",
        "v0_13_1_first_capability_intervention_pack_side_evidence_only",
    }
)
EXPECTED_V131_EFFECT_CLASSES = frozenset({"non_material", "side_evidence_only"})
EXPECTED_V131_HANDOFF_MODE = "determine_whether_stronger_bounded_capability_intervention_is_in_scope"

EXPECTED_V130_ADMITTED_INTERVENTION_IDS = frozenset(
    {
        "bounded_execution_strategy_upgrade_v1",
        "bounded_replan_search_control_upgrade_v1",
        "bounded_failure_diagnosis_upgrade_v1",
    }
)

CARRIED_DOMINANT_GAP_FAMILY = "residual_core_capability_gap"
EXPECTED_V115_FORMAL_LABEL = "product_gap_partial_but_interpretable"

ALLOWED_CANDIDATE_INTERVENTION_SHAPES = frozenset(
    {
        "stronger_l2_planner_strategy_upgrade",
        "stronger_search_budget_and_replan_control",
        "stronger_l3_l4_failure_diagnosis_chain",
        "mixed_bounded_capability_hardening",
        "none",
    }
)

SCOPE_STATUS_NO_STRONGER = "no_stronger_bounded_capability_intervention_in_scope"
SCOPE_STATUS_STRONGER_IN_SCOPE = "stronger_bounded_capability_intervention_still_in_scope"
SCOPE_STATUS_INVALID = "scope_assessment_invalid"

STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED = "justified"
STRONGER_CAPABILITY_INTERVENTION_STATUS_NOT_IN_SCOPE = "not_in_scope"
STRONGER_CAPABILITY_INTERVENTION_STATUS_INVALID = "invalid"

DEFAULT_NAMED_BLOCKER = (
    "admitted_bounded_intervention_set_covers_available_scope_and_residual_gap_requires_broader_capability_change"
)

DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE = {
    "broad_model_family_replacement_required": False,
    "task_base_widening_required": False,
    "same_source_comparison_break_required": False,
    "per_intervention_ablation_required_before_next_step": False,
    "admitted_intervention_families_already_exhausted": True,
}

__all__ = [
    "ALLOWED_CANDIDATE_INTERVENTION_SHAPES",
    "CARRIED_DOMINANT_GAP_FAMILY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_NAMED_BLOCKER",
    "DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE",
    "DEFAULT_REMAINING_CAPABILITY_INTERVENTION_SCOPE_ASSESSMENT_OUT_DIR",
    "DEFAULT_STRONGER_CAPABILITY_INTERVENTION_SCOPE_SUMMARY_OUT_DIR",
    "DEFAULT_V115_CLOSEOUT_PATH",
    "DEFAULT_V130_GOVERNANCE_PACK_PATH",
    "DEFAULT_V131_CLOSEOUT_PATH",
    "EXPECTED_V115_FORMAL_LABEL",
    "EXPECTED_V130_ADMITTED_INTERVENTION_IDS",
    "EXPECTED_V131_EFFECT_CLASSES",
    "EXPECTED_V131_HANDOFF_MODE",
    "EXPECTED_V131_VERSION_DECISIONS",
    "SCHEMA_PREFIX",
    "SCOPE_STATUS_INVALID",
    "SCOPE_STATUS_NO_STRONGER",
    "SCOPE_STATUS_STRONGER_IN_SCOPE",
    "STRONGER_CAPABILITY_INTERVENTION_STATUS_INVALID",
    "STRONGER_CAPABILITY_INTERVENTION_STATUS_JUSTIFIED",
    "STRONGER_CAPABILITY_INTERVENTION_STATUS_NOT_IN_SCOPE",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
