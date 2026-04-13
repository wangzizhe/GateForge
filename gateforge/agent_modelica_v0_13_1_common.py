from __future__ import annotations

from .agent_modelica_v0_8_0_common import REPO_ROOT, load_json, now_utc, write_json, write_text


SCHEMA_PREFIX = "agent_modelica_v0_13_1"

CURRENT_MAIN_EXECUTION_CHAIN = "agent_modelica_live_executor_v1"
DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

INTERVENTION_TOGGLE_ON = "on"
INTERVENTION_TOGGLE_OFF = "off"

INTERVENTION_EFFECT_MATERIAL = "material"
INTERVENTION_EFFECT_SIDE_EVIDENCE_ONLY = "side_evidence_only"
INTERVENTION_EFFECT_NON_MATERIAL = "non_material"
INTERVENTION_EFFECT_INVALID = "invalid"

EXPECTED_ADMITTED_INTERVENTION_IDS = frozenset(
    {
        "bounded_execution_strategy_upgrade_v1",
        "bounded_replan_search_control_upgrade_v1",
        "bounded_failure_diagnosis_upgrade_v1",
    }
)

DEFAULT_HANDOFF_INTEGRITY_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_handoff_integrity_current"
DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_capability_intervention_execution_pack_current"
)
DEFAULT_CAPABILITY_EFFECT_CHARACTERIZATION_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_capability_effect_characterization_current"
)
DEFAULT_CLOSEOUT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_closeout_current"

DEFAULT_PRE_INTERVENTION_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_pre_intervention_live_run_current"
)
DEFAULT_POST_INTERVENTION_RUN_OUT_DIR = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_1_post_intervention_live_run_current"
)

DEFAULT_V130_CLOSEOUT_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_closeout_current" / "summary.json"
DEFAULT_V130_GOVERNANCE_PACK_PATH = (
    REPO_ROOT / "artifacts" / "agent_modelica_v0_13_0_capability_intervention_governance_pack_current" / "summary.json"
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

EXPECTED_V130_VERSION_DECISION = "v0_13_0_capability_intervention_governance_ready"
EXPECTED_V130_HANDOFF_MODE = "execute_first_bounded_capability_intervention_pack"


__all__ = [
    "CURRENT_MAIN_EXECUTION_CHAIN",
    "DEFAULT_BUILDINGS_FIXTURE_HARDPACK_PATH",
    "DEFAULT_CAPABILITY_EFFECT_CHARACTERIZATION_OUT_DIR",
    "DEFAULT_CAPABILITY_INTERVENTION_EXECUTION_PACK_OUT_DIR",
    "DEFAULT_CLOSEOUT_OUT_DIR",
    "DEFAULT_DOCKER_IMAGE",
    "DEFAULT_HANDOFF_INTEGRITY_OUT_DIR",
    "DEFAULT_OPENIPSL_FIXTURE_HARDPACK_PATH",
    "DEFAULT_POST_INTERVENTION_RUN_OUT_DIR",
    "DEFAULT_PRE_INTERVENTION_RUN_OUT_DIR",
    "DEFAULT_V112_PRODUCT_GAP_SUBSTRATE_BUILDER_PATH",
    "DEFAULT_V130_CLOSEOUT_PATH",
    "DEFAULT_V130_GOVERNANCE_PACK_PATH",
    "EXPECTED_ADMITTED_INTERVENTION_IDS",
    "EXPECTED_V130_HANDOFF_MODE",
    "EXPECTED_V130_VERSION_DECISION",
    "INTERVENTION_EFFECT_INVALID",
    "INTERVENTION_EFFECT_MATERIAL",
    "INTERVENTION_EFFECT_NON_MATERIAL",
    "INTERVENTION_EFFECT_SIDE_EVIDENCE_ONLY",
    "INTERVENTION_TOGGLE_OFF",
    "INTERVENTION_TOGGLE_ON",
    "SCHEMA_PREFIX",
    "load_json",
    "now_utc",
    "write_json",
    "write_text",
]
