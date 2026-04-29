from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_memory_selection_tool_v0_34_4 import (
    dispatch_memory_selection_tool,
    get_memory_selection_tool_defs,
    record_semantic_memory_selection,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


class MemorySelectionToolV0344Tests(unittest.TestCase):
    def test_tool_records_selection_without_repair_authority(self) -> None:
        payload = json.loads(
            record_semantic_memory_selection(
                selected_unit_ids=["arrayed_measurement_flow_ownership"],
                rejected_unit_ids=["standard_library_semantic_substitution"],
                rationale="The compiler alternates between under and over constraints.",
                risk="Avoid symmetric current equations.",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertFalse(payload["auto_submit"])
        self.assertFalse(payload["retrieval_performed"])
        self.assertEqual(payload["selected_unit_count"], 1)

    def test_dispatch_rejects_unknown_tool(self) -> None:
        payload = json.loads(dispatch_memory_selection_tool("unknown", {}))
        self.assertIn("unknown_memory_selection_tool", payload["error"])

    def test_tool_def_is_available(self) -> None:
        defs = get_memory_selection_tool_defs()
        self.assertEqual(defs[0]["name"], "record_semantic_memory_selection")

    def test_harness_profile_exposes_memory_selection_tool(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("semantic_memory_selection")}
        self.assertIn("record_semantic_memory_selection", names)
        self.assertIn("check_model", names)
        guidance = get_tool_profile_guidance("semantic_memory_selection")
        self.assertIn("will not retrieve", guidance)


if __name__ == "__main__":
    unittest.main()
