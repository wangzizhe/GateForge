"""Unit tests for overdetermined mutation building v0.19.41.

Key differences from v0.19.40:
  - No comment on extra equation
  - Extra equation uses LARGE_VALUE = 1.0e10
  - _collect_mutations returns wrong_removal_text (original eq removed, extra kept)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_overdetermined_mutations_v0_19_41 import (
    LARGE_VALUE,
    _parse_equation_section,
    _collect_mutations,
    _is_overdetermined,
)

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

_MULTI_ALG = """\
model MultiAlg
  parameter Real k = 2.0  "gain";
  Real x(start = 0.0)  "state";
  Real a  "alg 1";
  Real b  "alg 2";
equation
  der(x) = -x;
  a = k * x;
  b = a + 1.0;
end MultiAlg;
"""


class TestCollectMutations(unittest.TestCase):

    def test_returns_tuple_five_elements(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        self.assertGreater(len(mutations), 0)
        self.assertEqual(len(mutations[0]), 5)

    def test_targets_algebraic_variable(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        var_names = [m[0] for m in mutations]
        self.assertIn("y", var_names)

    def test_does_not_target_state_variable(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        var_names = [m[0] for m in mutations]
        self.assertNotIn("x", var_names)

    def test_extra_equation_uses_large_value(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        _, mutated_text, _, _, _ = mutations[0]
        self.assertIn(LARGE_VALUE, mutated_text)

    def test_extra_equation_has_no_comment(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        _, mutated_text, _, _, _ = mutations[0]
        extra_line = next(
            l for l in mutated_text.splitlines() if LARGE_VALUE in l
        )
        self.assertNotIn("//", extra_line)

    def test_mutated_text_line_count_plus_one(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        _, mutated_text, _, _, _ = mutations[0]
        self.assertEqual(len(mutated_text.splitlines()), len(lines) + 1)

    def test_wrong_removal_same_line_count_as_source(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        _, _, wrong_text, _, _ = mutations[0]
        self.assertEqual(len(wrong_text.splitlines()), len(lines))

    def test_wrong_removal_contains_large_value(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        _, _, wrong_text, _, _ = mutations[0]
        self.assertIn(LARGE_VALUE, wrong_text)

    def test_wrong_removal_missing_original_equation(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        var_name, _, wrong_text, _, _ = mutations[0]
        # Original equation like "y = x;" should be gone
        self.assertNotIn(f"{var_name} = x;", wrong_text)

    def test_multi_alg_produces_two_mutations(self):
        lines = _MULTI_ALG.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        var_names = sorted(m[0] for m in mutations)
        self.assertEqual(var_names, ["a", "b"])

    def test_orig_start_end_indices_are_valid(self):
        lines = _BALANCED.splitlines()
        equations = _parse_equation_section(lines)
        mutations = _collect_mutations(lines, equations)
        _, _, _, orig_start, orig_end = mutations[0]
        self.assertGreaterEqual(orig_start, 0)
        self.assertLessEqual(orig_end, len(lines) - 1)
        self.assertLessEqual(orig_start, orig_end)


class TestIsOverdetermined(unittest.TestCase):

    def test_detects_overdetermined(self):
        self.assertTrue(_is_overdetermined("has 3 equation(s) and 2 variable(s)"))

    def test_balanced_not_overdetermined(self):
        self.assertFalse(_is_overdetermined("has 2 equation(s) and 2 variable(s)"))

    def test_underdetermined_not_overdetermined(self):
        self.assertFalse(_is_overdetermined("has 1 equation(s) and 2 variable(s)"))


if __name__ == "__main__":
    unittest.main()
