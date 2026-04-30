from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_residual_hypothesis_consistency_tool_v0_35_21 import (
    dispatch_residual_hypothesis_consistency_tool,
    get_residual_hypothesis_consistency_tool_defs,
    residual_hypothesis_consistency_check,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


OMC_OUTPUT = """
Warning: Variable probe.n[2].i does not have any remaining equation to be solved in.
Warning: Variable probe.n[1].i does not have any remaining equation to be solved in.
Warning: Variable probe.p[2].i does not have any remaining equation to be solved in.
Warning: Variable probe.p[1].i does not have any remaining equation to be solved in.
"""


class ResidualHypothesisConsistencyToolV03521Tests(unittest.TestCase):
    def test_flags_delta_larger_than_named_residual_without_patch(self) -> None:
        payload = json.loads(
            residual_hypothesis_consistency_check(
                omc_output=OMC_OUTPUT,
                expected_equation_delta=6,
                candidate_strategy="set all p[i].i and n[i].i to zero",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertEqual(payload["unmatched_flow_variable_count"], 4)
        self.assertTrue(payload["over_residual_delta"])

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_residual_hypothesis_consistency_tool_defs()}
        self.assertIn("residual_hypothesis_consistency_check", names)
        result = dispatch_residual_hypothesis_consistency_tool(
            "residual_hypothesis_consistency_check",
            {"omc_output": OMC_OUTPUT, "expected_equation_delta": 6, "candidate_strategy": "all zero"},
        )
        self.assertIn("over_residual_delta", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_residual_consistency_checkpoint")}
        self.assertIn("residual_hypothesis_consistency_check", profile_names)
        self.assertIn("consistency", get_tool_profile_guidance("connector_flow_residual_consistency_checkpoint"))


if __name__ == "__main__":
    unittest.main()
