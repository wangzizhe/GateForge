from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_connector_balance_tool_v0_29_9 import (
    connector_balance_diagnostic,
    dispatch_connector_balance_tool,
    get_connector_balance_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs


MODEL_TEXT = """
model ConnectorCase
  connector MeasurementPin
    Real v;
    flow Real i;
    flow Real iSense;
  end MeasurementPin;

  MeasurementPin p;
  MeasurementPin n;
  Real observedVoltage;
equation
  p.v = n.v;
  observedVoltage = p.v;
end ConnectorCase;
"""


class ConnectorBalanceToolV0299Tests(unittest.TestCase):
    def test_connector_balance_diagnostic_reports_risk_without_patch(self) -> None:
        payload = json.loads(connector_balance_diagnostic(MODEL_TEXT))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertEqual(payload["connectors"][0]["name"], "MeasurementPin")
        self.assertEqual(payload["connectors"][0]["flow_count"], 2)
        self.assertEqual(payload["connectors"][0]["potential_like_count"], 1)
        self.assertIn("MeasurementPin:flow_potential_count_mismatch", payload["risks"])
        self.assertIn("custom_connector_direct_field_equations_present", payload["risks"])

    def test_dispatch_rejects_empty_model(self) -> None:
        payload = json.loads(dispatch_connector_balance_tool("connector_balance_diagnostic", {"model_text": ""}))
        self.assertEqual(payload["error"], "empty_model_text")

    def test_tool_profile_adds_connector_diagnostic_only_when_requested(self) -> None:
        base_names = {tool["name"] for tool in get_tool_defs("base")}
        structural_names = {tool["name"] for tool in get_tool_defs("structural")}
        connector_names = {tool["name"] for tool in get_tool_defs("connector")}
        self.assertNotIn("connector_balance_diagnostic", base_names)
        self.assertNotIn("connector_balance_diagnostic", structural_names)
        self.assertIn("connector_balance_diagnostic", connector_names)

    def test_tool_definition_is_available(self) -> None:
        defs = get_connector_balance_tool_defs()
        self.assertEqual(defs[0]["name"], "connector_balance_diagnostic")


if __name__ == "__main__":
    unittest.main()
