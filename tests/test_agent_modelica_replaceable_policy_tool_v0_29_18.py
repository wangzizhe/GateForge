from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_replaceable_policy_tool_v0_29_18 import (
    dispatch_replaceable_policy_tool,
    replaceable_partial_policy_check,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


RISKY_MODEL = """
model PolicyCase
  partial model ProbeBase
    Modelica.Electrical.Analog.Interfaces.Pin p;
    Modelica.Electrical.Analog.Interfaces.Pin n;
  equation
    0 = p.i + n.i;
  end ProbeBase;

  model VoltProbe
    extends ProbeBase;
    Real v;
  equation
    v = p.v - n.v;
    0 = p.i + n.i;
  end VoltProbe;

  replaceable model Probe = VoltProbe constrainedby ProbeBase;
end PolicyCase;
"""


class ReplaceablePolicyToolV02918Tests(unittest.TestCase):
    def test_policy_check_flags_base_flow_duplicate_risk_without_patch(self) -> None:
        payload = json.loads(replaceable_partial_policy_check(RISKY_MODEL))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertEqual(payload["risk_count"], 1)
        self.assertEqual(
            payload["risks"][0]["risk"],
            "partial_base_flow_equation_duplicates_derived_flow_behavior",
        )

    def test_dispatch_rejects_empty_model(self) -> None:
        payload = json.loads(dispatch_replaceable_policy_tool("replaceable_partial_policy_check", {"model_text": ""}))
        self.assertEqual(payload["error"], "empty_model_text")

    def test_replaceable_policy_profile_exposes_policy_tool(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy")}
        self.assertIn("check_model", names)
        self.assertIn("replaceable_partial_diagnostic", names)
        self.assertIn("replaceable_partial_policy_check", names)
        self.assertNotIn("connector_balance_diagnostic", names)
        self.assertIn("replaceable_partial_policy_check", get_tool_profile_guidance("replaceable_policy"))


if __name__ == "__main__":
    unittest.main()
