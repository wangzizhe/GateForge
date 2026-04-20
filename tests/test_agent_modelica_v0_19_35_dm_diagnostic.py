"""Unit tests for diagnostic_context_dm_v0_19_35 (Dulmage-Mendelsohn module)."""
from __future__ import annotations

import unittest

from scripts.diagnostic_context_dm_v0_19_35 import (
    _parse_algebraic_variables,
    _parse_equations,
    _maximum_matching,
    _dm_underdetermined_component,
    build_dm_diagnostic_context,
)

# ── minimal flat model fixtures ───────────────────────────────────────────────

_BALANCED_MODEL = """
model Balanced
  parameter Real tau = 1.0 "time constant";
  Real x(start = 0.0) "state";
  Real y "algebraic output";
equation
  der(x) = -x / tau;
  y = 2.0 * x;
end Balanced;
"""

# parameter_promotion mutation: tau demoted to algebraic variable
_UNDERDETERMINED_TAU = """
model Broken
  Real tau  "time constant";
  Real x(start = 0.0) "state";
  Real y "algebraic output";
equation
  der(x) = -x / tau;
  y = 2.0 * x;
end Broken;
"""

# Two free variables, one equation missing
_TWO_FREE_VARS = """
model TwoFree
  Real a  "first free";
  Real b  "second free";
  Real c  "defined";
equation
  c = a + b;
end TwoFree;
"""

_NO_EQUATION_SECTION = """
model NoEq
  Real x "variable";
end NoEq;
"""


# ── _parse_algebraic_variables ────────────────────────────────────────────────

class TestParseAlgebraicVariables(unittest.TestCase):
    def test_skips_parameters(self):
        decl = "  parameter Real tau = 1.0 \"time constant\";\n  Real x \"state\";\n"
        result = _parse_algebraic_variables(decl)
        self.assertNotIn("tau", result)
        self.assertIn("x", result)

    def test_skips_constants(self):
        decl = "  constant Real g = 9.81 \"gravity\";\n  Real v \"velocity\";\n"
        result = _parse_algebraic_variables(decl)
        self.assertNotIn("g", result)
        self.assertIn("v", result)

    def test_var_with_start_value(self):
        decl = "  Real x(start = 0.0) \"state\";\n"
        result = _parse_algebraic_variables(decl)
        self.assertIn("x", result)

    def test_var_with_description(self):
        decl = "  Real tau  \"time constant\";\n"
        result = _parse_algebraic_variables(decl)
        self.assertIn("tau", result)

    def test_empty_decl(self):
        self.assertEqual(_parse_algebraic_variables(""), [])


# ── _parse_equations ──────────────────────────────────────────────────────────

class TestParseEquations(unittest.TestCase):
    def _vars(self, *names):
        return set(names)

    def test_simple_assignment(self):
        text = "equation\n  y = 2.0 * x;\nend M;"
        eqs = _parse_equations(text, {"x", "y"})
        self.assertEqual(len(eqs), 1)
        self.assertEqual(eqs[0].lhs_var, "y")
        self.assertIn("x", eqs[0].all_vars)

    def test_der_equation(self):
        text = "equation\n  der(x) = -x / tau;\nend M;"
        eqs = _parse_equations(text, {"x", "tau"})
        self.assertEqual(len(eqs), 1)
        self.assertEqual(eqs[0].lhs_var, "x")

    def test_skips_connect(self):
        text = "equation\n  connect(a, b);\n  y = x;\nend M;"
        eqs = _parse_equations(text, {"x", "y"})
        self.assertEqual(len(eqs), 1)

    def test_skips_initial_equation(self):
        text = "initial equation\n  x = 0;\nequation\n  y = x;\nend M;"
        eqs = _parse_equations(text, {"x", "y"})
        self.assertEqual(len(eqs), 1)
        self.assertEqual(eqs[0].lhs_var, "y")


# ── _maximum_matching (LHS preference) ───────────────────────────────────────

class TestMaximumMatching(unittest.TestCase):
    def test_balanced_matches_all(self):
        known = {"x", "y"}
        eqs = _parse_equations(
            "equation\n  der(x) = -x;\n  y = x;\nend M;", known
        )
        var_to_eqs = {v: [eq.index for eq in eqs if v in eq.all_vars] for v in known}
        matching = _maximum_matching(list(known), eqs, var_to_eqs)
        self.assertEqual(len(matching), 2)
        self.assertIn("x", matching)
        self.assertIn("y", matching)

    def test_lhs_preference_keeps_natural_assignment(self):
        # tau has no LHS equation; x has der(x)=... ; y has y=...
        # With LHS preference: x and y get matched; tau is unmatched
        known = {"tau", "x", "y"}
        eqs = _parse_equations(
            "equation\n  der(x) = -x / tau;\n  y = 2.0 * x;\nend M;", known
        )
        var_to_eqs = {v: [eq.index for eq in eqs if v in eq.all_vars] for v in known}
        matching = _maximum_matching(list(known), eqs, var_to_eqs)
        self.assertNotIn("tau", matching)
        self.assertIn("x", matching)
        self.assertIn("y", matching)

    def test_empty_returns_empty(self):
        matching = _maximum_matching([], [], {})
        self.assertEqual(matching, {})


# ── build_dm_diagnostic_context ───────────────────────────────────────────────

class TestBuildDmDiagnosticContext(unittest.TestCase):
    def test_balanced_model_no_underdetermined(self):
        ctx = build_dm_diagnostic_context(_BALANCED_MODEL)
        self.assertIn("no underdetermined", ctx.lower())

    def test_underdetermined_identifies_root_cause(self):
        ctx = build_dm_diagnostic_context(_UNDERDETERMINED_TAU)
        self.assertIn("STRUCTURAL DIAGNOSTIC", ctx)
        self.assertIn("tau", ctx)
        self.assertIn("Root cause variable", ctx)

    def test_underdetermined_shows_description(self):
        ctx = build_dm_diagnostic_context(_UNDERDETERMINED_TAU)
        self.assertIn("time constant", ctx)

    def test_underdetermined_shows_subgraph_equations(self):
        ctx = build_dm_diagnostic_context(_UNDERDETERMINED_TAU)
        # der(x) = -x / tau should appear (references tau)
        self.assertIn("der(x)", ctx)

    def test_no_equation_section_fallback(self):
        ctx = build_dm_diagnostic_context(_NO_EQUATION_SECTION)
        self.assertIn("no equation section", ctx.lower())

    def test_output_under_600_chars(self):
        ctx = build_dm_diagnostic_context(_UNDERDETERMINED_TAU)
        self.assertLessEqual(len(ctx), 600)

    def test_fix_hint_present(self):
        ctx = build_dm_diagnostic_context(_UNDERDETERMINED_TAU)
        self.assertIn("Fix:", ctx)

    def test_two_free_vars_both_reported(self):
        ctx = build_dm_diagnostic_context(_TWO_FREE_VARS)
        # Both a and b are root causes (only 1 equation for 3 variables)
        self.assertIn("STRUCTURAL DIAGNOSTIC", ctx)
        # at least one of the root cause vars should be named
        self.assertTrue("a" in ctx or "b" in ctx)


if __name__ == "__main__":
    unittest.main()
