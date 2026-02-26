from __future__ import annotations


SCHEMA_VERSION = "agent_modelica_difficulty_layer_spec_v1"

LAYER_1 = "layer_1"
LAYER_2 = "layer_2"
LAYER_3 = "layer_3"
LAYER_4 = "layer_4"

STAGE_SUBTYPE_NONE = "stage_0_none"
STAGE_SUBTYPE_PARSE = "stage_1_parse_syntax"
STAGE_SUBTYPE_STRUCTURAL = "stage_2_structural_balance_reference"
STAGE_SUBTYPE_STAGE3_TYPE_CONNECTOR = "stage_3_type_connector_consistency"
STAGE_SUBTYPE_STAGE3_BEHAVIORAL = "stage_3_behavioral_contract_semantic"
STAGE_SUBTYPE_STAGE3_LEGACY = "stage_3_type_connector_semantic"
STAGE_SUBTYPE_INIT = "stage_4_initialization_singularity"
STAGE_SUBTYPE_RUNTIME = "stage_5_runtime_numerical_instability"

STAGE_TO_DEFAULT_LAYER = {
    STAGE_SUBTYPE_PARSE: LAYER_1,
    STAGE_SUBTYPE_STRUCTURAL: LAYER_2,
    STAGE_SUBTYPE_STAGE3_TYPE_CONNECTOR: LAYER_2,
    STAGE_SUBTYPE_STAGE3_BEHAVIORAL: LAYER_3,
    STAGE_SUBTYPE_INIT: LAYER_4,
    STAGE_SUBTYPE_RUNTIME: LAYER_4,
}


def default_difficulty_layer_from_stage_subtype(stage_subtype: str) -> str:
    subtype = str(stage_subtype or "").strip().lower()
    if not subtype:
        return ""
    if subtype == STAGE_SUBTYPE_STAGE3_LEGACY:
        return LAYER_2
    return STAGE_TO_DEFAULT_LAYER.get(subtype, "")


def stage_subtype_default_layer_reason(stage_subtype: str) -> str:
    subtype = str(stage_subtype or "").strip().lower()
    if not subtype:
        return ""
    if subtype == STAGE_SUBTYPE_STAGE3_LEGACY:
        return "default_from_stage_subtype_legacy_stage3"
    if subtype in STAGE_TO_DEFAULT_LAYER:
        return "default_from_stage_subtype"
    return ""
