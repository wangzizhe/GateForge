from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_connector_contract_tool_v0_32_6 import (
    connector_contract_diagnostic,
    dispatch_connector_contract_tool,
    get_connector_contract_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance

MODEL_TEXT = """model ContractToy
  connector Pin
    Real v;
    flow Real i;
  end Pin;
  partial model Base
    Pin p[2];
    Pin n[2];
    output Real y[2];
  end Base;
  model Actual
    extends Base;
  equation
    for i in 1:2 loop
      y[i] = p[i].v - n[i].v;
    end for;
  end Actual;
  replaceable model Probe = Actual constrainedby Base;
  Pin rail;
  Pin groundPin;
  Probe probe;
equation
  for i in 1:2 loop
    connect(rail, probe.p[i]);
    connect(groundPin, probe.n[i]);
  end for;
end ContractToy;
"""


class ConnectorContractToolV0326Tests(unittest.TestCase):
    def test_connector_contract_diagnostic_reports_semantic_risks_without_patch(self) -> None:
        payload = json.loads(connector_contract_diagnostic(MODEL_TEXT))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertIn("Probe:base_exposes_arrayed_connector_fields", payload["semantic_risks"])
        self.assertIn("Probe:actual_reads_potential_without_flow_ownership", payload["semantic_risks"])
        self.assertGreaterEqual(payload["connect_summary"]["arrayed_connect_count"], 2)

    def test_dispatch_empty_model_returns_error(self) -> None:
        payload = json.loads(dispatch_connector_contract_tool("connector_contract_diagnostic", {}))
        self.assertIn("error", payload)

    def test_tool_profile_exposes_only_when_requested(self) -> None:
        names = {tool["name"] for tool in get_connector_contract_tool_defs()}
        self.assertEqual(names, {"connector_contract_diagnostic"})
        self.assertIn("connector_contract_diagnostic", {tool["name"] for tool in get_tool_defs("connector_contract")})
        self.assertNotIn("connector_contract_diagnostic", {tool["name"] for tool in get_tool_defs("base")})
        self.assertIn("connector_contract_diagnostic", get_tool_profile_guidance("connector_contract"))


if __name__ == "__main__":
    unittest.main()
