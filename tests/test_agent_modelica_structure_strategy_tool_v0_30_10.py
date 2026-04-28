from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_structure_strategy_tool_v0_30_10 import (
    dispatch_structure_strategy_tool,
    get_structure_strategy_tool_defs,
    record_structure_strategies,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class StructureStrategyToolV03010Tests(unittest.TestCase):
    def test_strategy_tool_is_diagnostic_only(self) -> None:
        payload = json.loads(
            record_structure_strategies(
                strategies=["move flow equation", "change constrainedby base"],
                selected_strategy="move flow equation",
                reason="Different equation ownership.",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertEqual(payload["unique_strategy_count"], 2)

    def test_dispatch_rejects_unknown_tool(self) -> None:
        payload = json.loads(dispatch_structure_strategy_tool("unknown", {}))
        self.assertIn("error", payload)

    def test_profile_exposes_strategy_tool(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_structure_plan_checkpoint")}
        self.assertIn("record_structure_strategies", names)
        self.assertIn("candidate_acceptance_critique", names)
        self.assertIn("structurally distinct", get_tool_profile_guidance("replaceable_policy_structure_plan_checkpoint"))
        self.assertEqual(get_structure_strategy_tool_defs()[0]["name"], "record_structure_strategies")


if __name__ == "__main__":
    unittest.main()
