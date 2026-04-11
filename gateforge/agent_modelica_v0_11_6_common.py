from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_11_6"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_6_handoff_integrity_current"
DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_6_remaining_uncertainty_characterization_current"
)
DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_6_bounded_product_gap_step_worth_it_summary_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_6_closeout_current"

DEFAULT_V115_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_11_5_closeout_current" / "summary.json"

BOUND_STEP_KIND_NONE = "none"
BOUND_STEP_KIND_TARGETED_CONTEXT_CONTRACT_CLARIFICATION = "targeted_context_contract_clarification"


__all__ = [
    "BOUND_STEP_KIND_NONE",
    "BOUND_STEP_KIND_TARGETED_CONTEXT_CONTRACT_CLARIFICATION",
    "DEFAULT_BOUNDED_PRODUCT_GAP_STEP_WORTH_IT_SUMMARY_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_REMAINING_UNCERTAINTY_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_V115_CLOSEOUT_PATH",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
