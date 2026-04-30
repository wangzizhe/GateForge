from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_arrayed_shared_bus_tool_v0_35_18 import (
    arrayed_shared_bus_diagnostic,
    dispatch_arrayed_shared_bus_tool,
    get_arrayed_shared_bus_tool_defs,
)
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


SAMPLE = """model Sample
  connector Pin
    Real v;
    flow Real i;
  end Pin;
  model Branch
    Pin a;
    Pin b;
  equation
    a.i + b.i = 0;
  end Branch;
  model ProbeBank
    Pin p[3];
    Pin n[3];
    output Real y[3];
  equation
    for i in 1:3 loop
      y[i] = p[i].v - n[i].v;
    end for;
  end ProbeBank;
  Pin rail;
  Pin ground;
  Branch branch[3];
  ProbeBank probe;
equation
  connect(rail, branch[1].a);
  connect(rail, branch[2].a);
  connect(rail, branch[3].a);
  connect(rail, probe.p[1]);
  connect(rail, probe.p[2]);
  connect(rail, probe.p[3]);
  connect(ground, branch[1].b);
  connect(ground, branch[2].b);
  connect(ground, branch[3].b);
  connect(ground, probe.n[1]);
  connect(ground, probe.n[2]);
  connect(ground, probe.n[3]);
end Sample;
"""


class ArrayedSharedBusToolV03518Tests(unittest.TestCase):
    def test_diagnostic_reports_large_arrayed_bus_without_patch(self) -> None:
        payload = json.loads(arrayed_shared_bus_diagnostic(SAMPLE))
        self.assertTrue(payload["diagnostic_only"])
        self.assertFalse(payload["patch_generated"])
        self.assertFalse(payload["candidate_selected"])
        self.assertGreaterEqual(payload["shared_bus_set_count"], 2)
        self.assertTrue(any(row["has_probe_array"] for row in payload["shared_bus_sets"]))

    def test_dispatch_and_profile_are_exposed(self) -> None:
        names = {tool["name"] for tool in get_arrayed_shared_bus_tool_defs()}
        self.assertIn("arrayed_shared_bus_diagnostic", names)
        result = dispatch_arrayed_shared_bus_tool("arrayed_shared_bus_diagnostic", {"model_text": SAMPLE})
        self.assertIn("shared_bus_sets", result)
        profile_names = {tool["name"] for tool in get_tool_defs("connector_flow_arrayed_bus_checkpoint")}
        self.assertIn("arrayed_shared_bus_diagnostic", profile_names)
        self.assertIn("arrayed shared-bus", get_tool_profile_guidance("connector_flow_arrayed_bus_checkpoint"))


if __name__ == "__main__":
    unittest.main()
