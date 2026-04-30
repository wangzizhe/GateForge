from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_equation_delta_portfolio_tool_v0_35_26 import (
    dispatch_equation_delta_portfolio_tool,
    get_equation_delta_portfolio_tool_defs,
    record_equation_delta_candidate_portfolio,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class EquationDeltaPortfolioToolV03526Tests(unittest.TestCase):
    def test_records_distinct_delta_candidates_without_patch(self) -> None:
        payload = json.loads(
            record_equation_delta_candidate_portfolio(
                compiler_named_residual_count=4,
                candidates=[
                    {"strategy": "all probe pins zero", "expected_equation_delta": 6, "rationale": "symmetry"},
                    {"strategy": "compiler-named pins zero", "expected_equation_delta": 4, "rationale": "residual"},
                ],
                selected_strategy="compiler-named pins zero",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertEqual(payload["candidate_count"], 2)
        self.assertTrue(payload["has_residual_matching_delta"])

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_equation_delta_portfolio_tool_defs()}
        self.assertIn("record_equation_delta_candidate_portfolio", names)
        result = dispatch_equation_delta_portfolio_tool(
            "record_equation_delta_candidate_portfolio",
            {
                "compiler_named_residual_count": 4,
                "candidates": [{"strategy": "s", "expected_equation_delta": 4, "rationale": "r"}],
                "selected_strategy": "s",
            },
        )
        self.assertIn("has_residual_matching_delta", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_delta_portfolio_checkpoint")}
        self.assertIn("record_equation_delta_candidate_portfolio", profile_names)
        self.assertIn("candidate portfolio", get_tool_profile_guidance("connector_flow_delta_portfolio_checkpoint"))


if __name__ == "__main__":
    unittest.main()
