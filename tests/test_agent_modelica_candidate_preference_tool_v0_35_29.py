from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_candidate_preference_tool_v0_35_29 import (
    dispatch_candidate_preference_tool,
    get_candidate_preference_tool_defs,
    record_candidate_preference_rationale,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class CandidatePreferenceToolV03529Tests(unittest.TestCase):
    def test_records_compiler_residual_preference_without_selecting_candidate(self) -> None:
        payload = json.loads(
            record_candidate_preference_rationale(
                selected_candidate="4 residual-matching equations",
                rejected_candidate="6 symmetric equations",
                selected_expected_equation_delta=4,
                rejected_expected_equation_delta=6,
                compiler_named_residual_count=4,
                preference_basis="compiler_residual_match",
                why_compiler_evidence_wins_or_loses="OMC names four residuals.",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["candidate_selected"])
        self.assertTrue(payload["selected_matches_residual_count"])
        self.assertTrue(payload["compiler_evidence_preferred"])

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_candidate_preference_tool_defs()}
        self.assertIn("record_candidate_preference_rationale", names)
        result = dispatch_candidate_preference_tool(
            "record_candidate_preference_rationale",
            {
                "selected_candidate": "a",
                "rejected_candidate": "b",
                "selected_expected_equation_delta": 4,
                "rejected_expected_equation_delta": 6,
                "compiler_named_residual_count": 4,
                "preference_basis": "compiler_residual_match",
                "why_compiler_evidence_wins_or_loses": "r",
            },
        )
        self.assertIn("compiler_evidence_preferred", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_candidate_preference_checkpoint")}
        self.assertIn("record_candidate_preference_rationale", profile_names)
        self.assertIn("candidate preference", get_tool_profile_guidance("connector_flow_candidate_preference_checkpoint"))


if __name__ == "__main__":
    unittest.main()
