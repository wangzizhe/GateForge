from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_12_1"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_handoff_integrity_current"
DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_remedy_execution_pack_current"
DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_pack_effect_characterization_current"
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_closeout_current"

DEFAULT_PRE_REMEDY_RUN_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_pre_remedy_live_run_current"
DEFAULT_POST_REMEDY_RUN_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_1_post_remedy_live_run_current"

DEFAULT_V120_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_12_0_closeout_current" / "summary.json"
DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_product_gap_substrate_builder_current" / "summary.json"
)

DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH = (
    REPO_ROOT / "assets_private" / "agent_modelica_cross_domain_buildings_v1_fixture_v1" / "hardpack_frozen.json"
)
DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH = (
    REPO_ROOT / "assets_private" / "agent_modelica_cross_domain_openipsl_v1_fixture_v1" / "hardpack_frozen.json"
)

EXPECTED_V120_VERSION_DECISION = "v0_12_0_operational_remedy_governance_ready"
EXPECTED_V120_HANDOFF_MODE = "execute_first_bounded_operational_remedy_pack"

EXPECTED_FIRST_REMEDY_IDS = (
    "workflow_goal_reanchoring_hardening",
    "dynamic_prompt_field_stability_hardening",
    "full_omc_error_visibility_hardening",
)

PACK_EFFECT_MAINLINE_IMPROVING = "mainline_improving"
PACK_EFFECT_SIDE_EVIDENCE_ONLY = "side_evidence_only"
PACK_EFFECT_NON_MATERIAL = "non_material"
PACK_EFFECT_INVALID = "invalid"

REMEDY_TOGGLE_ON = "on"
REMEDY_TOGGLE_OFF = "off"

__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DOCKER_IMAGE",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH",
    "DEFAULT_PACK_EFFECT_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_POST_REMEDY_RUN_OUT_DIR",
    "DEFAULT_PRE_REMEDY_RUN_OUT_DIR",
    "DEFAULT_REMEDY_EXECUTION_PACK_OUT_DIR",
    "DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH",
    "DEFAULT_V120_CLOSEOUT_PATH",
    "EXPECTED_FIRST_REMEDY_IDS",
    "EXPECTED_V120_HANDOFF_MODE",
    "EXPECTED_V120_VERSION_DECISION",
    "PACK_EFFECT_INVALID",
    "PACK_EFFECT_MAINLINE_IMPROVING",
    "PACK_EFFECT_NON_MATERIAL",
    "PACK_EFFECT_SIDE_EVIDENCE_ONLY",
    "REMEDY_TOGGLE_OFF",
    "REMEDY_TOGGLE_ON",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
