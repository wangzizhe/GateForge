from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_connector_flow_state_tool_v0_35_9 import (
    connector_flow_state_diagnostic,
    dispatch_connector_flow_state_tool,
    get_connector_flow_state_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


SAMPLE = """model Sample
  connector Pin
    Real v;
    flow Real i;
  end Pin;
  model Probe
    Pin p;
    Pin n;
    output Real y;
  equation
    y = p.v - n.v;
  end Probe;
  model Load
    Pin p;
    Pin n;
  equation
    p.i = (p.v - n.v) / 10;
    n.i = -p.i;
  end Load;
  Pin source;
  Pin sink;
  Load load;
  Probe probe;
equation
  source.v = 1;
  sink.v = 0;
  connect(source, load.p);
  connect(probe.p, load.p);
  connect(load.n, sink);
  connect(probe.n, sink);
end Sample;
"""


class ConnectorFlowStateToolV0359Tests(unittest.TestCase):
    def test_diagnostic_reports_connection_sets_without_patch(self) -> None:
        payload = json.loads(connector_flow_state_diagnostic(SAMPLE))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertGreaterEqual(len(payload["connection_sets"]), 2)
        self.assertGreaterEqual(len(payload["flow_owner_rows"]), 2)

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_connector_flow_state_tool_defs()}
        self.assertIn("connector_flow_state_diagnostic", names)
        result = dispatch_connector_flow_state_tool("connector_flow_state_diagnostic", {"model_text": SAMPLE})
        self.assertIn("connection_sets", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_state_checkpoint")}
        self.assertIn("connector_flow_state_diagnostic", profile_names)
        self.assertIn("semantic state", get_tool_profile_guidance("connector_flow_state_checkpoint"))


if __name__ == "__main__":
    unittest.main()
