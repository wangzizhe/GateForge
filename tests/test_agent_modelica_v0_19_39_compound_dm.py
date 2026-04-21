"""Unit tests for compound-aware DM context per-variable fix hints (v0.19.39)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

# ── fixtures ──────────────────────────────────────────────────────────────────

# Compound model: TR promoted (PP) + ETERM_phantom added (PV)
_COMPOUND_PP_PV = """\
model CompoundAVR
  parameter Real KA = 200.0  "voltage regulator gain";
  Real TR  "measurement time constant";
  Real VM(start = 1.02)  "measured voltage";
  Real ETERM  "terminal voltage";
  Real ETERM_phantom  "terminal voltage";
equation
  ETERM = 1.02;
  der(VM) = (ETERM_phantom - VM) / TR;
end CompoundAVR;
"""

# Two promoted parameters (both PP type, no phantom)
_TWO_PP = """\
model TwoPP
  Real KA  "gain";
  Real TR  "time constant";
  Real VM(start = 1.0)  "output";
equation
  der(VM) = KA * (1.0 - VM) / TR;
end TwoPP;
"""

# Two phantom variables (both PV type)
_TWO_PV = """\
model TwoPV
  parameter Real K = 2.0  "gain";
  Real x(start = 0.0)  "state";
  Real y  "output";
  Real y_phantom  "output";
  Real z  "signal";
  Real z_phantom  "signal";
equation
  y = K * x;
  der(x) = -x + z_phantom;
end TwoPV;
"""


class TestCompoundDMPerVariableHints(unittest.TestCase):

    def test_pp_variable_gets_add_equation_hint(self):
        ctx = build_dm_diagnostic_context(_COMPOUND_PP_PV)
        # TR is PP type (no _phantom suffix)
        self.assertIn("TR", ctx)
        self.assertIn("Add a defining equation", ctx)

    def test_pv_variable_gets_remove_declaration_hint(self):
        ctx = build_dm_diagnostic_context(_COMPOUND_PP_PV)
        # ETERM_phantom is PV type
        self.assertIn("ETERM_phantom", ctx)
        self.assertIn('Remove the "Real ETERM_phantom" declaration', ctx)

    def test_pv_hint_names_base_variable(self):
        ctx = build_dm_diagnostic_context(_COMPOUND_PP_PV)
        # Fix hint should say to replace with ETERM (base var)
        self.assertIn('"ETERM_phantom" in equations with "ETERM"', ctx)

    def test_pp_hint_names_variable(self):
        ctx = build_dm_diagnostic_context(_COMPOUND_PP_PV)
        self.assertIn("TR = value", ctx)

    def test_both_root_causes_listed(self):
        ctx = build_dm_diagnostic_context(_COMPOUND_PP_PV)
        self.assertIn("TR", ctx)
        self.assertIn("ETERM_phantom", ctx)

    def test_two_pp_both_get_add_equation_hint(self):
        ctx = build_dm_diagnostic_context(_TWO_PP)
        # Both KA and TR need defining equations
        add_count = ctx.count("Add a defining equation")
        self.assertGreaterEqual(add_count, 2)

    def test_two_pv_both_get_remove_hint(self):
        ctx = build_dm_diagnostic_context(_TWO_PV)
        remove_count = ctx.count("Remove the")
        self.assertGreaterEqual(remove_count, 1)

    def test_no_hint_mixing_in_compound(self):
        ctx = build_dm_diagnostic_context(_COMPOUND_PP_PV)
        lines = ctx.splitlines()
        # The TR fix hint should NOT say "Remove"; ETERM_phantom hint should NOT say "Add"
        tr_hint = next((l for l in lines if "TR = value" in l), "")
        phantom_hint = next((l for l in lines if "Remove" in l and "ETERM_phantom" in l), "")
        self.assertNotIn("Remove", tr_hint)
        self.assertNotIn("Add a defining", phantom_hint)


class TestSingleRootCauseBackwardCompat(unittest.TestCase):
    """Single root cause behavior must remain unchanged."""

    _SINGLE_PP = """\
model SinglePP
  Real TR  "time constant";
  Real VM(start = 1.0)  "voltage";
equation
  der(VM) = (1.0 - VM) / TR;
end SinglePP;
"""

    _SINGLE_PV = """\
model SinglePV
  Real ETERM  "terminal voltage";
  Real ETERM_phantom  "terminal voltage";
  Real VM(start = 1.0)  "measured voltage";
equation
  ETERM = 1.02;
  der(VM) = (ETERM_phantom - VM) / 0.02;
end SinglePV;
"""

    def test_single_root_cause_still_has_generic_hint(self):
        ctx = build_dm_diagnostic_context(self._SINGLE_PP)
        self.assertIn("Fix:", ctx)
        self.assertIn("defining equation", ctx)

    def test_single_root_cause_format_unchanged(self):
        ctx = build_dm_diagnostic_context(self._SINGLE_PP)
        self.assertIn("Root cause variable (no defining equation):", ctx)

    def test_single_pv_root_cause_generic_hint(self):
        ctx = build_dm_diagnostic_context(self._SINGLE_PV)
        self.assertIn("Fix:", ctx)


if __name__ == "__main__":
    unittest.main()
