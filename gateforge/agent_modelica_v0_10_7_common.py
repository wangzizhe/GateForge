from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_10_7"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_7_handoff_integrity_current"
DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_7_remaining_uncertainty_characterization_current"
)
DEFAULT_BOUNDED_REAL_ORIGIN_STEP_WORTH_IT_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_10_7_bounded_real_origin_step_worth_it_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_7_closeout_current"

DEFAULT_V106_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_10_6_closeout_current" / "summary.json"

BOUND_STEP_KIND_NONE = "none"
BOUND_STEP_KIND_TARGETED_NON_SUCCESS_FAMILY_CLARIFICATION = "targeted_non_success_family_clarification"


__all__ = [
    "BOUND_STEP_KIND_NONE",
    "BOUND_STEP_KIND_TARGETED_NON_SUCCESS_FAMILY_CLARIFICATION",
    "DEFAULT_BOUNDED_REAL_ORIGIN_STEP_WORTH_IT_SUMMARY_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_V106_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
