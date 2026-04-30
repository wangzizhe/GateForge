from __future__ import annotations

import unittest

from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class ResidualRevisionProfileV03523Tests(unittest.TestCase):
    def test_profile_exposes_existing_diagnostics_and_revision_guidance(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("connector_flow_residual_revision_checkpoint")}
        self.assertIn("omc_unmatched_flow_diagnostic", names)
        self.assertIn("residual_hypothesis_consistency_check", names)
        guidance = get_tool_profile_guidance("connector_flow_residual_revision_checkpoint")
        self.assertIn("revised repair hypothesis", guidance)
        self.assertIn("do not generate patches", guidance)


if __name__ == "__main__":
    unittest.main()
