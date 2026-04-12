from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_12_2"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_2_handoff_integrity_current"
DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_12_2_remaining_remedy_scope_assessment_current"
)
DEFAULT_STRONGER_REMEDY_SCOPE_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_12_2_stronger_remedy_scope_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_2_closeout_current"

DEFAULT_V121_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_closeout_current" / "summary.json"

EXPECTED_V121_VERSION_DECISION = "v0_12_1_first_remedy_pack_non_material"
EXPECTED_V121_PACK_LEVEL_EFFECT = "non_material"
EXPECTED_V121_HANDOFF_MODE = "determine_whether_stronger_remedy_is_in_scope"

CARRIED_DOMINANT_GAP_FAMILY = "residual_core_capability_gap"

ALLOWED_CANDIDATE_REMEDY_SHAPES = frozenset(
    [
        "stronger_context_contract_hardening",
        "stronger_protocol_shell_hardening",
        "stronger_error_visibility_hardening",
        "mixed_bounded_operational_hardening",
        "none",
    ]
)

SCOPE_STATUS_NO_STRONGER = "no_stronger_bounded_remedy_in_scope"
SCOPE_STATUS_STRONGER_IN_SCOPE = "stronger_bounded_remedy_still_in_scope"
SCOPE_STATUS_INVALID = "scope_assessment_invalid"

STRONGER_REMEDY_STATUS_JUSTIFIED = "justified"
STRONGER_REMEDY_STATUS_NOT_IN_SCOPE = "not_in_scope"
STRONGER_REMEDY_STATUS_INVALID = "invalid"

DEFAULT_NAMED_BLOCKER = (
    "residual_core_capability_gap_requires_capability_level_improvement_not_shell_hardening"
)

DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE = {
    "broad_capability_rewrite_required": True,
    "task_base_widening_required": False,
    "same_source_comparison_break_required": False,
    "per_remedy_ablation_required_before_next_step": False,
    "unbounded_prompt_architecture_change_required": False,
}

__all__ = [
    "ALLOWED_CANDIDATE_REMEDY_SHAPES",
    "CARRIED_DOMINANT_GAP_FAMILY",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_NAMED_BLOCKER",
    "DEFAULT_OUT_OF_SCOPE_TRIGGER_TABLE",
    "DEFAULT_REMAINING_REMEDY_SCOPE_ASSESSMENT_OUT_DIR",
    "DEFAULT_STRONGER_REMEDY_SCOPE_SUMMARY_OUT_DIR",
    "DEFAULT_V121_CLOSEOUT_PATH",
    "EXPECTED_V121_HANDOFF_MODE",
    "EXPECTED_V121_PACK_LEVEL_EFFECT",
    "EXPECTED_V121_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "SCOPE_STATUS_INVALID",
    "SCOPE_STATUS_NO_STRONGER",
    "SCOPE_STATUS_STRONGER_IN_SCOPE",
    "STRONGER_REMEDY_STATUS_INVALID",
    "STRONGER_REMEDY_STATUS_JUSTIFIED",
    "STRONGER_REMEDY_STATUS_NOT_IN_SCOPE",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
