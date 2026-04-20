"""Unit tests for DM diagnostic context on phantom_variable models (v0.19.36)."""
from __future__ import annotations

import unittest

from scripts.diagnostic_context_dm_v0_19_35 import (
    _parse_algebraic_variables,
    _parse_equations,
    _maximum_matching,
    build_dm_diagnostic_context,
)

# ── phantom_variable model fixtures ──────────────────────────────────────────

# Mutation: ETERM_phantom added; replaces ETERM in der(VM) equation.
# ETERM still has its own equation (ETERM = ETERM_set), so ETERM_phantom
# has no defining equation → root cause.
_PHANTOM_ETERM = """
model PhantomEterm
  parameter Real TR = 0.02   "voltage measurement time constant";
  parameter Real ETERM_set = 1.02 "terminal voltage setpoint";
  Real ETERM     "terminal voltage input";
  Real ETERM_phantom  "phantom terminal voltage input";
  Real VM(start = 1.02) "measured terminal voltage";
equation
  ETERM = ETERM_set;
  der(VM) = (ETERM_phantom - VM) / TR;
end PhantomEterm;
"""

# Phantom variable that also appears in multiple equations.
_PHANTOM_MULTI_USE = """
model PhantomMulti
  parameter Real K = 2.0  "gain";
  Real x(start = 0.0) "state";
  Real y  "output";
  Real y_phantom  "phantom output";
equation
  der(x) = -x + y_phantom;
  y = K * x;
end PhantomMulti;
"""

# Balanced model — no phantom, should report no underdetermined.
_BALANCED = """
model Balanced
  parameter Real tau = 1.0 "time constant";
  Real x(start = 0.0) "state";
  Real y "output";
equation
  der(x) = -x / tau;
  y = x;
end Balanced;
"""

# Two phantom variables added simultaneously.
_TWO_PHANTOMS = """
model TwoPhantoms
  parameter Real A = 1.0 "param";
  Real x(start = 0.0) "state";
  Real x_p1  "phantom 1";
  Real x_p2  "phantom 2";
equation
  der(x) = -x_p1 - x_p2;
end TwoPhantoms;
"""


# ── DM root cause identification for phantom_variable ────────────────────────

class TestPhantomDmRootCause(unittest.TestCase):

    def test_phantom_identified_as_root_cause(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        self.assertIn("STRUCTURAL DIAGNOSTIC", ctx)
        self.assertIn("ETERM_phantom", ctx)

    def test_original_variable_not_root_cause(self):
        # ETERM has its own equation, so it should NOT be flagged
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        lines = ctx.splitlines()
        root_cause_line = next((l for l in lines if "Root cause variable" in l), "")
        self.assertIn("ETERM_phantom", root_cause_line)
        self.assertNotIn("ETERM ", root_cause_line)

    def test_phantom_description_shown(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        self.assertIn("phantom terminal voltage input", ctx)

    def test_fix_hint_present(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        self.assertIn("Fix:", ctx)

    def test_fix_hint_mentions_defining_equation(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        self.assertIn("defining equation", ctx)

    def test_balanced_no_underdetermined(self):
        ctx = build_dm_diagnostic_context(_BALANCED)
        self.assertIn("no underdetermined", ctx.lower())

    def test_phantom_multi_use_identified(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_MULTI_USE)
        self.assertIn("y_phantom", ctx)
        # y_phantom should be the root cause, not y (y has its own equation)
        lines = ctx.splitlines()
        root_line = next((l for l in lines if "Root cause variable" in l), "")
        self.assertIn("y_phantom", root_line)
        self.assertNotIn(" y ", root_line)  # bare "y" should not be root cause

    def test_two_phantoms_both_reported(self):
        ctx = build_dm_diagnostic_context(_TWO_PHANTOMS)
        self.assertIn("STRUCTURAL DIAGNOSTIC", ctx)
        self.assertTrue("x_p1" in ctx or "x_p2" in ctx)

    def test_output_under_600_chars(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        self.assertLessEqual(len(ctx), 600)

    def test_subgraph_equation_references_phantom(self):
        ctx = build_dm_diagnostic_context(_PHANTOM_ETERM)
        # der(VM) = (ETERM_phantom - VM) / TR; should appear as subgraph eq
        self.assertIn("ETERM_phantom", ctx)
        self.assertIn("VM", ctx)


# ── LHS preference: original variable should win over phantom ────────────────

class TestLhsPreferenceWithPhantom(unittest.TestCase):

    def test_eterm_matched_not_phantom(self):
        # ETERM has LHS equation (ETERM = ETERM_set), ETERM_phantom does not.
        # After matching: ETERM matched, ETERM_phantom unmatched.
        known = {"ETERM", "ETERM_phantom", "VM"}
        eqs = _parse_equations(
            "equation\n"
            "  ETERM = 1.02;\n"
            "  der(VM) = (ETERM_phantom - VM) / 0.02;\n"
            "end M;",
            known,
        )
        var_to_eqs = {v: [eq.index for eq in eqs if v in eq.all_vars] for v in known}
        matching = _maximum_matching(list(known), eqs, var_to_eqs)
        self.assertIn("ETERM", matching)
        self.assertIn("VM", matching)
        self.assertNotIn("ETERM_phantom", matching)

    def test_phantom_suffix_not_in_variable_list_if_absent(self):
        decl = "  Real x \"state\";\n  Real y \"output\";\n"
        result = _parse_algebraic_variables(decl)
        self.assertNotIn("x_phantom", result)


if __name__ == "__main__":
    unittest.main()
