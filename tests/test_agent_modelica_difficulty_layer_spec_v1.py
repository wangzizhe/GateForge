import unittest

from gateforge.agent_modelica_difficulty_layer_spec_v1 import (
    LAYER_2,
    LAYER_3,
    default_difficulty_layer_from_stage_subtype,
    stage_subtype_default_layer_reason,
)


class AgentModelicaDifficultyLayerSpecV1Tests(unittest.TestCase):
    def test_default_difficulty_layer_maps_refined_stage3_subtypes(self) -> None:
        self.assertEqual(
            default_difficulty_layer_from_stage_subtype("stage_3_type_connector_consistency"),
            LAYER_2,
        )
        self.assertEqual(
            default_difficulty_layer_from_stage_subtype("stage_3_behavioral_contract_semantic"),
            LAYER_3,
        )

    def test_default_difficulty_layer_maps_legacy_stage3_to_layer2(self) -> None:
        self.assertEqual(
            default_difficulty_layer_from_stage_subtype("stage_3_type_connector_semantic"),
            LAYER_2,
        )
        self.assertEqual(
            stage_subtype_default_layer_reason("stage_3_type_connector_semantic"),
            "default_from_stage_subtype_legacy_stage3",
        )


if __name__ == "__main__":
    unittest.main()
