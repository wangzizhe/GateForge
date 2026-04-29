from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_final_decision_record_tool_v0_34_13 import (
    dispatch_final_decision_record_tool,
    get_final_decision_record_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import dispatch_tool, get_tool_defs


class FinalDecisionRecordToolV03413Tests(unittest.TestCase):
    def test_tool_def_and_harness_profile_are_available(self) -> None:
        defs = get_final_decision_record_tool_defs()
        self.assertEqual(defs[0]["name"], "record_final_decision_rationale")
        profile_names = {
            tool["name"]
            for tool in get_tool_defs("reusable_contract_oracle_final_decision")
        }
        self.assertIn("reusable_contract_oracle_diagnostic", profile_names)
        self.assertIn("record_final_decision_rationale", profile_names)
        self.assertIn("submit_final", profile_names)

    def test_tool_records_decision_without_repair_authority(self) -> None:
        payload = json.loads(
            dispatch_final_decision_record_tool(
                "record_final_decision_rationale",
                {
                    "decision": "submit",
                    "evidence": ["OMC simulation passed", "contract oracle passed"],
                    "remaining_blockers": [],
                    "rationale": "No explicit blocker remains.",
                },
            )
        )
        self.assertTrue(payload["decision_recorded"])
        self.assertEqual(payload["decision"], "submit")
        self.assertFalse(payload["has_remaining_blockers"])
        self.assertFalse(payload["discipline"]["auto_submit"])
        self.assertFalse(payload["discipline"]["candidate_selected"])
        self.assertFalse(payload["discipline"]["patch_generated"])

    def test_dispatch_rejects_incomplete_record(self) -> None:
        payload = json.loads(
            dispatch_tool(
                "record_final_decision_rationale",
                {
                    "decision": "submit",
                    "evidence": [],
                    "remaining_blockers": [],
                    "rationale": "No evidence.",
                },
            )
        )
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
