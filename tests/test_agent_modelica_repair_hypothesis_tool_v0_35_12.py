from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_repair_hypothesis_tool_v0_35_12 import (
    dispatch_repair_hypothesis_tool,
    get_repair_hypothesis_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class RepairHypothesisToolV03512Tests(unittest.TestCase):
    def test_records_hypothesis_without_patch(self) -> None:
        result = json.loads(
            dispatch_repair_hypothesis_tool(
                "record_repair_hypothesis",
                {
                    "semantic_type": "connector_flow_ownership",
                    "target_boundary": "probe contract",
                    "candidate_strategy": "test local flow ownership constraints",
                    "expected_equation_delta": 2,
                    "fallback_hypothesis": "try topology boundary",
                },
            )
        )
        self.assertTrue(result["hypothesis_recorded"])
        self.assertFalse(result["discipline"]["patch_generated"])
        self.assertFalse(result["discipline"]["candidate_selected"])

    def test_profile_exposes_hypothesis_tool(self) -> None:
        names = {tool["name"] for tool in get_repair_hypothesis_tool_defs()}
        self.assertIn("record_repair_hypothesis", names)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_hypothesis_checkpoint")}
        self.assertIn("record_repair_hypothesis", profile_names)
        self.assertIn("repair hypothesis", get_tool_profile_guidance("connector_flow_hypothesis_checkpoint"))

    def test_minimal_contract_profile_is_exposed(self) -> None:
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_minimal_contract_checkpoint")}
        self.assertIn("record_repair_hypothesis", profile_names)
        guidance = get_tool_profile_guidance("connector_flow_minimal_contract_checkpoint")
        self.assertIn("minimal", guidance)
        self.assertIn("over-constraining", guidance)


if __name__ == "__main__":
    unittest.main()
