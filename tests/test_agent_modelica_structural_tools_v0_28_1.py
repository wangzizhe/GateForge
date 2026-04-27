from __future__ import annotations

import json
import unittest

from gateforge.agent_modelica_structural_tools_v0_28_1 import (
    declared_but_unused,
    dispatch_structural_tool,
    get_structural_tool_defs,
    get_unmatched_vars,
    who_defines,
    who_uses,
)

SIMPLE_MODEL = """model Simple
  Real x;
  Real y;
equation
  x = 1.0;
  y = x + 1.0;
end Simple;
"""

UNDERDETERMINED_MODEL = """model Under
  Real x;
  Real y;
  Real z;
equation
  x = 1.0;
  y = x + z;
end Under;
"""

PHANTOM_MODEL = """model Phantom
  Real x;
  Real x_phantom;
  Real y;
equation
  y = 1.0;
  x_phantom = y + 1.0;
end Phantom;
"""


class StructuralToolsV0281Tests(unittest.TestCase):
    def test_tool_defs_count(self) -> None:
        defs = get_structural_tool_defs()
        names = {t["name"] for t in defs}
        self.assertIn("who_defines", names)
        self.assertIn("who_uses", names)
        self.assertIn("declared_but_unused", names)
        self.assertIn("get_unmatched_vars", names)

    def test_who_defines_finds_lhs(self) -> None:
        result = json.loads(who_defines(SIMPLE_MODEL, "x"))
        self.assertEqual(result["count"], 1)
        self.assertIn("x = 1.0", result["equations"][0])

    def test_who_defines_var_not_on_lhs(self) -> None:
        result = json.loads(who_defines(SIMPLE_MODEL, "y"))
        self.assertEqual(result["count"], 1)
        self.assertIn("y = x + 1.0", result["equations"][0])

    def test_who_uses_finds_rhs_references(self) -> None:
        result = json.loads(who_uses(SIMPLE_MODEL, "x"))
        self.assertEqual(result["count"], 1)
        self.assertIn("y = x + 1.0", result["equations"][0])

    def test_who_uses_no_references(self) -> None:
        result = json.loads(who_uses(SIMPLE_MODEL, "y"))
        self.assertEqual(result["count"], 0)

    def test_declared_but_unused_detects_phantom(self) -> None:
        result = json.loads(declared_but_unused(PHANTOM_MODEL))
        self.assertIn("x", result["unused_vars"])
        self.assertEqual(result["count"], 1)

    def test_declared_but_unused_none_in_clean_model(self) -> None:
        result = json.loads(declared_but_unused(SIMPLE_MODEL))
        self.assertEqual(result["count"], 0)

    def test_get_unmatched_vars_under_model(self) -> None:
        result = get_unmatched_vars(UNDERDETERMINED_MODEL)
        self.assertIn("z", result)
        self.assertIn("Root cause variable", result)

    def test_get_unmatched_vars_clean_model(self) -> None:
        result = get_unmatched_vars(SIMPLE_MODEL)
        self.assertIn("no underdetermined variables", result)

    def test_dispatch_structural_unknown_tool(self) -> None:
        result = dispatch_structural_tool("nonexistent", {"model_text": SIMPLE_MODEL})
        self.assertIn("unknown_structural_tool", result)

    def test_dispatch_who_defines(self) -> None:
        result = dispatch_structural_tool("who_defines", {"model_text": SIMPLE_MODEL, "var_name": "x"})
        parsed = json.loads(result)
        self.assertEqual(parsed["count"], 1)

    def test_dispatch_empty_model_text(self) -> None:
        result = dispatch_structural_tool("who_defines", {"model_text": "", "var_name": "x"})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
