from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_candidate_critique_tool_v0_30_0 import (
    candidate_acceptance_critique,
    dispatch_candidate_critique_tool,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class CandidateCritiqueToolV0300Tests(unittest.TestCase):
    def test_critique_reports_no_encoded_blocker_without_patch(self) -> None:
        payload = json.loads(candidate_acceptance_critique(omc_passed=True, concern="I am worried physically."))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertFalse(payload["auto_submit"])
        self.assertEqual(payload["verdict"], "no_encoded_blocker_found")

    def test_critique_detects_constraint_citation(self) -> None:
        payload = json.loads(
            candidate_acceptance_critique(
                omc_passed=True,
                task_constraints=["Preserve the intended power-related measurement."],
                concern="This may violate the task constraint to preserve the intended power-related measurement.",
            )
        )
        self.assertEqual(payload["verdict"], "review_named_constraint")
        self.assertTrue(payload["constraint_citation_seen"])

    def test_dispatch_rejects_unknown_tool(self) -> None:
        payload = json.loads(dispatch_candidate_critique_tool("unknown", {}))
        self.assertIn("unknown_candidate_critique_tool", payload["error"])

    def test_candidate_critique_profile_is_exposed(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_candidate_critique")}
        self.assertIn("candidate_acceptance_critique", names)
        self.assertIn("candidate critique", get_tool_profile_guidance("replaceable_policy_candidate_critique"))


if __name__ == "__main__":
    unittest.main()
