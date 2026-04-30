from __future__ import annotations

import unittest

from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class DeltaCoverageProfileV03527Tests(unittest.TestCase):
    def test_profile_requires_residual_delta_coverage_without_patch_generation(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("connector_flow_delta_coverage_checkpoint")}
        self.assertIn("record_equation_delta_candidate_portfolio", names)
        self.assertIn("residual_hypothesis_consistency_check", names)
        guidance = get_tool_profile_guidance("connector_flow_delta_coverage_checkpoint")
        self.assertIn("exactly matches", guidance)
        self.assertIn("do not generate patches", guidance)


if __name__ == "__main__":
    unittest.main()
