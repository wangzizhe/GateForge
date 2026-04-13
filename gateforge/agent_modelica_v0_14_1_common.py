from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_14_1"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

BROADER_CHANGE_TOGGLE_ON = "on"
BROADER_CHANGE_TOGGLE_OFF = "off"

BROADER_CHANGE_EFFECT_MATERIAL = "mainline_material"
BROADER_CHANGE_EFFECT_SIDE_EVIDENCE_ONLY = "side_evidence_only"
BROADER_CHANGE_EFFECT_NON_MATERIAL = "non_material"
BROADER_CHANGE_EFFECT_INVALID = "invalid"

EXPECTED_ADMITTED_BROADER_CHANGE_IDS = frozenset(
    {
        "broader_L2_execution_policy_restructuring_v1",
        "governed_llm_backbone_upgrade_v1",
    }
)

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_handoff_integrity_current"
DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_broader_change_execution_pack_current"
)
DEFAULT_BROADER_CHANGE_EFFECT_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_broader_change_effect_characterization_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_closeout_current"

DEFAULT_PRE_BROADER_CHANGE_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_pre_broader_change_live_run_current"
)
DEFAULT_POST_BROADER_CHANGE_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_1_post_broader_change_live_run_current"
)

DEFAULT_V140_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_closeout_current" / "summary.json"
DEFAULT_V140_GOVERNANCE_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_14_0_broader_change_governance_pack_current" / "summary.json"
)
DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_11_2_product_gap_substrate_builder_current" / "summary.json"
)

DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH = (
    REPO_ROOT / "assets_private" / "agent_modelica_cross_domain_buildings_v1_fixture_v1" / "hardpack_frozen.json"
)
DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH = (
    REPO_ROOT / "assets_private" / "agent_modelica_cross_domain_openipsl_v1_fixture_v1" / "hardpack_frozen.json"
)

EXPECTED_V140_VERSION_DECISION = "v0_14_0_broader_change_governance_ready"
EXPECTED_V140_HANDOFF_MODE = "execute_first_broader_change_pack"


__all__ = [
    "BROADER_CHANGE_EFFECT_INVALID",
    "BROADER_CHANGE_EFFECT_MATERIAL",
    "BROADER_CHANGE_EFFECT_NON_MATERIAL",
    "BROADER_CHANGE_EFFECT_SIDE_EVIDENCE_ONLY",
    "BROADER_CHANGE_TOGGLE_OFF",
    "BROADER_CHANGE_TOGGLE_ON",
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "DEFAULT_BROADER_CHANGE_EFFECT_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_BROADER_CHANGE_EXECUTION_PACK_OUT_DIR",
    "DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DOCKER_IMAGE",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH",
    "DEFAULT_POST_BROADER_CHANGE_RUN_OUT_DIR",
    "DEFAULT_PRE_BROADER_CHANGE_RUN_OUT_DIR",
    "DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH",
    "DEFAULT_V140_CLOSEOUT_PATH",
    "DEFAULT_V140_GOVERNANCE_PACK_PATH",
    "EXPECTED_ADMITTED_BROADER_CHANGE_IDS",
    "EXPECTED_V140_HANDOFF_MODE",
    "EXPECTED_V140_VERSION_DECISION",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
