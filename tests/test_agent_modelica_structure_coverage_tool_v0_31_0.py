from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_structure_coverage_tool_v0_31_0 import (
    dispatch_structure_coverage_tool,
    get_structure_coverage_tool_defs,
    structure_coverage_diagnostic,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


def _model(flow_count: int) -> str:
    flows = "\n".join(f"  p{i}.i = 0;" for i in range(flow_count))
    return f"model X\n  connector Pin\n    flow Real i;\n  end Pin;\n  Pin p0;\nequation\n{flows}\nend X;"


class StructureCoverageToolV0310Tests(unittest.TestCase):
    def test_structure_coverage_reports_clusters_without_patch(self) -> None:
        payload = json.loads(
            structure_coverage_diagnostic(
                candidates=[
                    {"label": "a", "model_text": _model(1)},
                    {"label": "b", "model_text": _model(2)},
                    {"label": "a_dup", "model_text": _model(1)},
                ],
                focus="flow ownership",
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertEqual(payload["candidate_count"], 3)
        self.assertEqual(payload["structure_cluster_count"], 2)
        self.assertEqual(payload["duplicate_candidate_count"], 1)

    def test_dispatch_rejects_unknown_tool(self) -> None:
        payload = json.loads(dispatch_structure_coverage_tool("unknown", {}))
        self.assertIn("error", payload)

    def test_tool_definition_is_exposed(self) -> None:
        self.assertEqual(get_structure_coverage_tool_defs()[0]["name"], "structure_coverage_diagnostic")

    def test_tool_use_profile_exposes_coverage_tool(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_structure_coverage_checkpoint")}
        guidance = get_tool_profile_guidance("replaceable_policy_structure_coverage_checkpoint")
        self.assertIn("structure_coverage_diagnostic", names)
        self.assertIn("candidate_acceptance_critique", names)
        self.assertIn("structural clusters", guidance)


if __name__ == "__main__":
    unittest.main()
