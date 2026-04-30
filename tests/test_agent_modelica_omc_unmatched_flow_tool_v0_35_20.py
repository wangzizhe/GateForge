from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_omc_unmatched_flow_tool_v0_35_20 import (
    dispatch_omc_unmatched_flow_tool,
    get_omc_unmatched_flow_tool_defs,
    omc_unmatched_flow_diagnostic,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


OMC_OUTPUT = """
Warning: Variable probe.n[2].i does not have any remaining equation to be solved in.
Warning: Variable probe.n[1].i does not have any remaining equation to be solved in.
Warning: Variable probe.p[2].i does not have any remaining equation to be solved in.
Warning: Variable probe.p[1].i does not have any remaining equation to be solved in.
"""


class OmcUnmatchedFlowToolV03520Tests(unittest.TestCase):
    def test_extracts_unmatched_flow_variables_without_patch(self) -> None:
        payload = json.loads(omc_unmatched_flow_diagnostic(OMC_OUTPUT))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertEqual(payload["unmatched_flow_variable_count"], 4)
        self.assertEqual({row["array_root"] for row in payload["flow_variable_groups"]}, {"probe.n[].i", "probe.p[].i"})

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_omc_unmatched_flow_tool_defs()}
        self.assertIn("omc_unmatched_flow_diagnostic", names)
        result = dispatch_omc_unmatched_flow_tool("omc_unmatched_flow_diagnostic", {"omc_output": OMC_OUTPUT})
        self.assertIn("unmatched_flow_variables", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_omc_named_checkpoint")}
        self.assertIn("omc_unmatched_flow_diagnostic", profile_names)
        self.assertIn("compiler-named", get_tool_profile_guidance("connector_flow_omc_named_checkpoint"))


if __name__ == "__main__":
    unittest.main()
