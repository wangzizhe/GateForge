from __future__ import annotations

import unittest

from gateforge.agent_modelica_representation_view_v1 import (
    build_blt_proxy_view,
    build_causal_view,
    format_blt_proxy_view,
    format_causal_view,
)


MODEL_TEXT = """
model RepToy
  parameter Real K = 2.0;
  parameter Real T;
  Real x;
  Real y;
  Real z_phantom;
equation
  der(x) = -x + y;
  y = K + z_phantom;
end RepToy;
"""


OMC_OUTPUT = """
Error: Too few equations, under-determined system. The model has 2 equation(s) and 5 variable(s).
[/workspace/RepToy.mo:5:3-5:18:writable] Warning: Variable z_phantom does not have any remaining equation to be solved in.
  The original equations were:
  Equation 2: y = K + z_phantom, which needs to solve for y
"""


class TestRepresentationViews(unittest.TestCase):

    def test_build_causal_view(self) -> None:
        view = build_causal_view(model_text=MODEL_TEXT, omc_output=OMC_OUTPUT)
        self.assertIn("z_phantom", view["undersolved_variables"])
        self.assertIn("z_phantom", view["selected_variables"])
        self.assertIn("T", view["unbound_parameters"])

    def test_format_causal_view_is_factual(self) -> None:
        view = build_causal_view(model_text=MODEL_TEXT, omc_output=OMC_OUTPUT)
        text = format_causal_view(view)
        self.assertIn("modelica_causal_view", text)
        self.assertIn("variable: z_phantom", text)
        self.assertNotIn("should delete", text.lower())
        self.assertNotIn("root cause", text.lower())

    def test_build_blt_proxy_view(self) -> None:
        view = build_blt_proxy_view(model_text=MODEL_TEXT, omc_output=OMC_OUTPUT)
        self.assertGreaterEqual(view["block_count"], 1)
        self.assertIn("z_phantom", view["undersolved_variables"])

    def test_format_blt_proxy_view(self) -> None:
        view = build_blt_proxy_view(model_text=MODEL_TEXT, omc_output=OMC_OUTPUT)
        text = format_blt_proxy_view(view)
        self.assertIn("modelica_blt_proxy_view", text)
        self.assertIn("block_count", text)
        self.assertNotIn("should restore", text.lower())


if __name__ == "__main__":
    unittest.main()

