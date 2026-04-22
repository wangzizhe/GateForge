"""Unit tests for hard case analysis (v0.19.47).

Covers:
  - OMC eq/var count extraction
  - Diff stats computation
  - Stalled failure mode classification
"""
from __future__ import annotations

import unittest

from scripts.analyze_hard_cases_v0_19_47 import (
    _classify_stalled_failure_mode,
    _compute_diff_stats,
    _extract_eq_var_counts,
)


class TestExtractEqVarCounts(unittest.TestCase):

    def test_parses_standard_omc_output(self) -> None:
        text = 'Class Model has 11 equation(s) and 14 variable(s).'
        eq, var = _extract_eq_var_counts(text)
        self.assertEqual(eq, 11)
        self.assertEqual(var, 14)

    def test_returns_none_when_no_match(self) -> None:
        eq, var = _extract_eq_var_counts("some random text")
        self.assertIsNone(eq)
        self.assertIsNone(var)


class TestComputeDiffStats(unittest.TestCase):

    def test_identical_texts(self) -> None:
        stats = _compute_diff_stats("a\nb\nc", "a\nb\nc")
        self.assertEqual(stats["diff_lines"], 0)

    def test_one_line_diff(self) -> None:
        stats = _compute_diff_stats("a\nb\nc", "a\nX\nc")
        self.assertEqual(stats["diff_lines"], 1)

    def test_length_mismatch(self) -> None:
        stats = _compute_diff_stats("a\nb", "a\nb\nc")
        self.assertEqual(stats["diff_lines"], 1)


class TestClassifyStalledFailureMode(unittest.TestCase):

    def test_type_a_no_attempt(self) -> None:
        attempts = [
            {"model_changed": False, "pp1_state_after": "not_attempted"},
        ]
        self.assertEqual(_classify_stalled_failure_mode(attempts, "", ""), "type_a_no_attempt")

    def test_type_b2_incomplete(self) -> None:
        attempts = [
            {"model_changed": True, "pp1_state_after": "not_attempted", "patched_model_path": ""},
            {"model_changed": True, "pp1_state_after": "attempted_incomplete", "patched_model_path": ""},
            {"model_changed": False, "pp1_state_after": "fixed", "patched_model_path": ""},
        ]
        self.assertEqual(_classify_stalled_failure_mode(attempts, "", ""), "type_b2_incomplete")

    def test_type_c_cycling(self) -> None:
        attempts = [
            {"model_changed": True, "pp1_state_after": "attempted_incomplete", "patched_model_path": ""},
            {"model_changed": True, "pp1_state_after": "not_attempted", "patched_model_path": ""},
            {"model_changed": True, "pp1_state_after": "attempted_incomplete", "patched_model_path": ""},
        ]
        self.assertEqual(_classify_stalled_failure_mode(attempts, "", ""), "type_c_cycling")


if __name__ == "__main__":
    unittest.main()
