from __future__ import annotations

import unittest

from gateforge.agent_modelica_live_executor_v1 import (
    _repair_overdetermined_added_binding_equation,
    _rewrite_legacy_msl_siunits_patch,
)


class V0197BoundedResidualRepairTests(unittest.TestCase):
    def test_rewrites_legacy_msl_siunits_types_to_real(self) -> None:
        patched = (
            "model M\n"
            "  parameter Modelica.SIunits.Resistance gateforge_R = 100.0;\n"
            "  parameter Modelica.SIunits.Capacitance gateforge_C = 0.01;\n"
            "end M;\n"
        )

        rewritten, audit = _rewrite_legacy_msl_siunits_patch(patched)

        self.assertTrue(audit["applied"])
        self.assertIn("Modelica.SIunits.Resistance", audit["rewritten_references"])
        self.assertIn("parameter Real gateforge_R = 100.0;", rewritten)
        self.assertIn("parameter Real gateforge_C = 0.01;", rewritten)
        self.assertNotIn("Modelica.SIunits", rewritten)

    def test_rewrite_guard_noops_without_legacy_reference(self) -> None:
        patched = "model M\n  parameter Real R = 100.0;\nend M;\n"

        rewritten, audit = _rewrite_legacy_msl_siunits_patch(patched)

        self.assertFalse(audit["applied"])
        self.assertEqual(rewritten, patched)

    def test_overdetermined_repair_removes_added_binding_equation(self) -> None:
        source = (
            "model M\n"
            "  Real x;\n"
            "equation\n"
            "  der(x) = 1.0;\n"
            "end M;\n"
        )
        current = (
            "model M\n"
            "  Real x;\n"
            "equation\n"
            "  x = 0.0;\n"
            "  der(x) = 1.0;\n"
            "end M;\n"
        )
        output = "Error: Too many equations, over-determined system."

        repaired, audit = _repair_overdetermined_added_binding_equation(
            current_text=current,
            source_model_text=source,
            output=output,
        )

        self.assertTrue(audit["applied"])
        self.assertEqual(audit["removed_line"], "x = 0.0;")
        self.assertNotIn("  x = 0.0;", repaired)
        self.assertIn("  der(x) = 1.0;", repaired)

    def test_overdetermined_repair_does_not_remove_source_equation(self) -> None:
        source = (
            "model M\n"
            "  Real x;\n"
            "equation\n"
            "  x = 0.0;\n"
            "end M;\n"
        )

        repaired, audit = _repair_overdetermined_added_binding_equation(
            current_text=source,
            source_model_text=source,
            output="Error: Too many equations, over-determined system.",
        )

        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "no_added_non_connect_binding_equation_found")
        self.assertEqual(repaired, source)


if __name__ == "__main__":
    unittest.main()
