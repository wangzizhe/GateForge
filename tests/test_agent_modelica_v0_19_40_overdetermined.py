"""Unit tests for overdetermined mutation building and diagnostic context (v0.19.40)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_overdetermined_mutations_v0_19_40 import (
    _parse_equation_section,
    _collect_extra_equation_mutations,
    _is_overdetermined,
)
from scripts.diagnostic_context_overdetermined_v0_19_40 import (
    build_overdetermined_diagnostic_context,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

_BALANCED = """\
model Balanced
  parameter Real tau = 1.0  "time constant";
  Real x(start = 0.0)  "state";
  Real y  "output";
equation
  der(x) = -x / tau;
  y = x;
end Balanced;
"""

# Overdetermined: y has two defining equations
_OVERDET_Y = """\
model OverdetY
  parameter Real tau = 1.0  "time constant";
  Real x(start = 0.0)  "state";
  Real y  "output";
equation
  der(x) = -x / tau;
  y = x;
  y = 0.0;  // overdetermined: extra conflicting equation
end OverdetY;
"""

# Two over-constrained variables
_OVERDET_TWO = """\
model OverdetTwo
  Real x(start = 0.0)  "state";
  Real y  "output";
  Real z  "signal";
equation
  der(x) = -x;
  y = x;
  y = 0.0;
  z = y;
  z = 0.0;
end OverdetTwo;
"""


class TestCollectExtraEquationMutations(unittest.TestCase):

    def test_finds_algebraic_variables_with_equations(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_extra_equation_mutations(lines, equations)
        var_names = [v for v, _ in mutations]
        self.assertIn("y", var_names)

    def test_does_not_target_state_variables(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_extra_equation_mutations(lines, equations)
        var_names = [v for v, _ in mutations]
        # x has start= so it's a state variable, should NOT be targeted
        self.assertNotIn("x", var_names)

    def test_mutated_text_contains_extra_equation(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_extra_equation_mutations(lines, equations)
        self.assertGreater(len(mutations), 0)
        _, mutated_text = mutations[0]
        self.assertIn("= 0.0;", mutated_text)

    def test_mutated_text_line_count_increased_by_one(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_extra_equation_mutations(lines, equations)
        _, mutated_text = mutations[0]
        self.assertEqual(len(mutated_text.splitlines()), len(lines) + 1)


class TestIsOverdetermined(unittest.TestCase):

    def test_detects_overdetermined_count(self):
        output = 'Class X has 3 equation(s) and 2 variable(s).'
        self.assertTrue(_is_overdetermined(output))

    def test_balanced_not_overdetermined(self):
        output = 'Class X has 2 equation(s) and 2 variable(s).'
        self.assertFalse(_is_overdetermined(output))

    def test_underdetermined_not_overdetermined(self):
        output = 'Class X has 1 equation(s) and 2 variable(s).'
        self.assertFalse(_is_overdetermined(output))


class TestBuildOverdeterminedDiagnosticContext(unittest.TestCase):

    def test_balanced_model_no_over_constrained(self):
        ctx = build_overdetermined_diagnostic_context(_BALANCED)
        self.assertIn("no variable", ctx.lower())

    def test_overdet_identifies_variable(self):
        ctx = build_overdetermined_diagnostic_context(_OVERDET_Y)
        self.assertIn("STRUCTURAL DIAGNOSTIC", ctx)
        self.assertIn("y", ctx)

    def test_overdet_shows_both_equations(self):
        ctx = build_overdetermined_diagnostic_context(_OVERDET_Y)
        self.assertIn("Eq 1:", ctx)
        self.assertIn("Eq 2:", ctx)

    def test_overdet_labels_redundant_equation(self):
        ctx = build_overdetermined_diagnostic_context(_OVERDET_Y)
        self.assertIn("redundant", ctx.lower())

    def test_overdet_fix_hint_present(self):
        ctx = build_overdetermined_diagnostic_context(_OVERDET_Y)
        self.assertIn("Fix:", ctx)
        self.assertIn("Remove", ctx)

    def test_overdet_two_variables_both_reported(self):
        ctx = build_overdetermined_diagnostic_context(_OVERDET_TWO)
        self.assertIn("y", ctx)
        self.assertIn("z", ctx)

    def test_overdet_shows_original_description(self):
        ctx = build_overdetermined_diagnostic_context(_OVERDET_Y)
        self.assertIn("output", ctx)


if __name__ == "__main__":
    unittest.main()
