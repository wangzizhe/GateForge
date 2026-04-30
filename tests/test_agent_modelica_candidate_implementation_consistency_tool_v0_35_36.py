from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_candidate_implementation_consistency_tool_v0_35_36 import (
    candidate_implementation_consistency_check,
    dispatch_candidate_implementation_consistency_tool,
    get_candidate_implementation_consistency_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class CandidateImplementationConsistencyToolV03536Tests(unittest.TestCase):
    def test_detects_loop_expanded_zero_flow_mismatch_without_patch(self) -> None:
        model_text = "model X equation for i in 1:2 loop p[i].i = 0; n[i].i = 0; end for; end X;"
        payload = json.loads(
            candidate_implementation_consistency_check(
                candidate_model_text=model_text,
                expected_equation_delta=2,
                candidate_strategy="two equations",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertEqual(payload["implemented_zero_flow_equation_count"], 4)
        self.assertFalse(payload["implementation_matches_expected_delta"])

    def test_deficit_match_when_delta_equals_omc_gap(self) -> None:
        model_text = "model X equation p.i = 0; end X;"
        omc = 'Check of X completed successfully.\nClass X has 1 equation(s) and 2 variable(s).'
        payload = json.loads(
            candidate_implementation_consistency_check(
                candidate_model_text=model_text,
                expected_equation_delta=1,
                candidate_strategy="one zero flow",
                omc_output=omc,
            )
        )
        self.assertEqual(payload["omc_reported_deficit"], 1)
        self.assertTrue(payload["deficit_matches_expected_delta"])
        self.assertTrue(payload["implementation_matches_expected_delta"])

    def test_deficit_mismatch_detected_when_delta_exceeds_gap(self) -> None:
        model_text = "model X equation p.i = 0; end X;"
        omc = 'Check of X completed successfully.\nClass X has 1 equation(s) and 2 variable(s).'
        payload = json.loads(
            candidate_implementation_consistency_check(
                candidate_model_text=model_text,
                expected_equation_delta=3,
                candidate_strategy="too many",
                omc_output=omc,
            )
        )
        self.assertEqual(payload["omc_reported_deficit"], 1)
        self.assertFalse(payload["deficit_matches_expected_delta"])
        self.assertIn("over-determined", payload["interpretation"][1])

    def test_deficit_skipped_when_no_omc_output(self) -> None:
        payload = json.loads(
            candidate_implementation_consistency_check(
                candidate_model_text="model X equation end X;",
                expected_equation_delta=1,
                candidate_strategy="small",
            )
        )
        self.assertIsNone(payload["omc_reported_deficit"])
        self.assertIsNone(payload["deficit_matches_expected_delta"])
        self.assertIn("skipped", payload["interpretation"][1])

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_candidate_implementation_consistency_tool_defs()}
        self.assertIn("candidate_implementation_consistency_check", names)
        result = dispatch_candidate_implementation_consistency_tool(
            "candidate_implementation_consistency_check",
            {
                "candidate_model_text": "model X equation p.i = 0; end X;",
                "expected_equation_delta": 1,
                "candidate_strategy": "one zero flow",
            },
        )
        self.assertIn("implementation_matches_expected_delta", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_candidate_implementation_checkpoint")}
        self.assertIn("candidate_implementation_consistency_check", profile_names)
        self.assertIn("implementation consistency", get_tool_profile_guidance("connector_flow_candidate_implementation_checkpoint"))


if __name__ == "__main__":
    unittest.main()
