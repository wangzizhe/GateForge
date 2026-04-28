from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_replaceable_partial_tool_v0_29_16 import (
    dispatch_replaceable_partial_tool,
    replaceable_partial_diagnostic,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


MODEL_TEXT = """
model ReplaceableCase
  partial model ProbeBase
    Modelica.Electrical.Analog.Interfaces.Pin p;
    Modelica.Electrical.Analog.Interfaces.Pin n;
  end ProbeBase;

  model VoltProbe
    extends ProbeBase;
    Real v;
  equation
    v = p.v - n.v;
    0 = p.i + n.i;
  end VoltProbe;

  replaceable model Probe[2] = VoltProbe constrainedby ProbeBase;
end ReplaceableCase;
"""


class ReplaceablePartialToolV02916Tests(unittest.TestCase):
    def test_replaceable_partial_diagnostic_reports_risks_without_patch(self) -> None:
        payload = json.loads(replaceable_partial_diagnostic(MODEL_TEXT))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertEqual(payload["replaceable_declarations"][0]["name"], "Probe")
        self.assertIn("Probe:replaceable_array", payload["risks"])
        self.assertIn("Probe:constrainedby_partial_base", payload["risks"])
        self.assertIn("Probe:actual_adds_flow_equations_not_present_in_base", payload["risks"])

    def test_dispatch_rejects_empty_model(self) -> None:
        payload = json.loads(dispatch_replaceable_partial_tool("replaceable_partial_diagnostic", {"model_text": ""}))
        self.assertEqual(payload["error"], "empty_model_text")

    def test_replaceable_profile_exposes_only_narrow_tool(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable")}
        self.assertIn("check_model", names)
        self.assertIn("replaceable_partial_diagnostic", names)
        self.assertNotIn("get_unmatched_vars", names)
        self.assertNotIn("connector_balance_diagnostic", names)
        self.assertIn("replaceable_partial_diagnostic", get_tool_profile_guidance("replaceable"))


if __name__ == "__main__":
    unittest.main()
