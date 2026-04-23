from __future__ import annotations

import unittest

from gateforge.agent_modelica_tool_context_v1 import (
    build_modelica_query_tool_context,
    extract_omc_no_equation_variables,
    format_modelica_query_tool_context,
)


MODEL_TEXT = """
model ToolToy
  parameter Real K = 2.0;
  parameter Real MissingParameter;
  Real x;
  Real y;
  Real z_phantom;
  Real unused_local;
equation
  der(x) = -x + y;
  y = K + z_phantom + ETERM;
end ToolToy;
"""


OMC_OUTPUT = """
Error: Too few equations, under-determined system. The model has 2 equation(s) and 5 variable(s).
[/workspace/ToolToy.mo:6:3-6:18:writable] Warning: Variable z_phantom does not have any remaining equation to be solved in.
  The original equations were:
  Equation 2: y = K + z_phantom + ETERM, which needs to solve for y
[/workspace/ToolToy.mo:4:3-4:9:writable] Warning: Variable MissingParameter does not have any remaining equation to be solved in.
  The original equations were:
  Equation 2: y = K + MissingParameter, which needs to solve for y
"""


class TestToolContext(unittest.TestCase):

    def test_extracts_omc_no_equation_variables(self) -> None:
        self.assertEqual(
            extract_omc_no_equation_variables(OMC_OUTPUT),
            ["z_phantom", "MissingParameter"],
        )

    def test_build_context_selects_omc_and_structural_variables(self) -> None:
        context = build_modelica_query_tool_context(
            model_text=MODEL_TEXT,
            omc_output=OMC_OUTPUT,
        )
        self.assertEqual(
            context["omc_no_equation_variables"],
            ["z_phantom", "MissingParameter"],
        )
        selected = context["selected_variables"]
        self.assertIn("z_phantom", selected)
        self.assertIn("MissingParameter", selected)
        self.assertIn("unused_local", selected)

    def test_phantom_is_no_defining_equation_not_declared_but_unused(self) -> None:
        context = build_modelica_query_tool_context(
            model_text=MODEL_TEXT,
            omc_output=OMC_OUTPUT,
        )
        summary = context["summary"]
        self.assertIn("z_phantom", summary["variables_with_no_defining_equation"])
        self.assertNotIn("z_phantom", summary["declared_but_unused"])

    def test_formats_factual_block(self) -> None:
        context = build_modelica_query_tool_context(
            model_text=MODEL_TEXT,
            omc_output=OMC_OUTPUT,
        )
        formatted = format_modelica_query_tool_context(context)
        self.assertIn("modelica_query_tool_observations", formatted)
        self.assertIn("variable: z_phantom", formatted)
        self.assertIn("variables_with_no_defining_equation", formatted)
        self.assertNotIn("should delete", formatted.lower())
        self.assertNotIn("should restore", formatted.lower())
        self.assertNotIn("root cause", formatted.lower())

    def test_limits_selected_variables(self) -> None:
        context = build_modelica_query_tool_context(
            model_text=MODEL_TEXT,
            omc_output=OMC_OUTPUT,
            max_variables=2,
        )
        self.assertEqual(len(context["selected_variables"]), 2)


if __name__ == "__main__":
    unittest.main()

