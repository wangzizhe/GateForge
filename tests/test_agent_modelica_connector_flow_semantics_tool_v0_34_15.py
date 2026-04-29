from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_connector_flow_semantics_tool_v0_34_15 import (
    connector_flow_semantics_diagnostic,
    dispatch_connector_flow_semantics_tool,
    get_connector_flow_semantics_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import dispatch_tool, get_tool_defs, get_tool_profile_guidance


MODEL_TEXT = """model X
  connector Pin
    Real v;
    flow Real i;
  end Pin;
  model Probe
    Pin p[2];
    Pin n[2];
    output Real y[2];
  equation
    for i in 1:2 loop
      y[i] = p[i].v - n[i].v;
    end for;
    p[1].i + n[1].i = 0;
    p[2].i + n[2].i = 0;
  end Probe;
  Pin rail;
  Pin groundPin;
  Probe probe;
equation
  connect(rail, probe.p[1]);
  connect(rail, probe.p[2]);
  connect(groundPin, probe.n[1]);
  connect(groundPin, probe.n[2]);
end X;"""


class ConnectorFlowSemanticsToolV03415Tests(unittest.TestCase):
    def test_tool_def_and_harness_profile_are_available(self) -> None:
        defs = get_connector_flow_semantics_tool_defs()
        self.assertEqual(defs[0]["name"], "connector_flow_semantics_diagnostic")
        names = {tool["name"] for tool in get_tool_defs("connector_flow_semantics")}
        self.assertIn("check_model", names)
        self.assertIn("simulate_model", names)
        self.assertIn("submit_final", names)
        self.assertIn("connector_flow_semantics_diagnostic", names)
        self.assertIn("diagnostic", get_tool_profile_guidance("connector_flow_semantics"))

    def test_reports_balanced_without_simulation_success_risk(self) -> None:
        payload = json.loads(
            connector_flow_semantics_diagnostic(
                MODEL_TEXT,
                'Class X has 24 equation(s) and 24 variable(s).\nrecord SimulationResult resultFile = ""',
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertFalse(payload["submitted"])
        self.assertTrue(payload["omc_state"]["balanced_equation_count"])
        self.assertIn("balanced_equation_count_without_simulation_success", payload["semantic_risks"])
        self.assertIn("Probe:paired_flow_balance_may_balance_counts_without_unique_semantics", payload["semantic_risks"])

    def test_dispatch_rejects_empty_model(self) -> None:
        payload = json.loads(dispatch_connector_flow_semantics_tool("connector_flow_semantics_diagnostic", {}))
        self.assertEqual(payload["error"], "empty_model_text")

    def test_harness_dispatch_routes_tool(self) -> None:
        payload = json.loads(
            dispatch_tool(
                "connector_flow_semantics_diagnostic",
                {
                    "model_text": MODEL_TEXT,
                    "omc_output": 'Class X has 24 equation(s) and 24 variable(s). resultFile = ""',
                },
            )
        )
        self.assertTrue(payload["diagnostic_only"])
        self.assertGreaterEqual(payload["risk_count"], 1)


if __name__ == "__main__":
    unittest.main()
