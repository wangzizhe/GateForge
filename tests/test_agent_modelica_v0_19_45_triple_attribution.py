"""Unit tests for triple underdetermined five-valued attribution (v0.19.45).

States:
  not_attempted / attempted_incomplete / structural_fixed
  / structural_fixed_behavioral_incomplete / behavioral_fixed

Also covers:
  - Pattern builders (_structural_fix_pattern, _behavioral_fix_pattern, _attempt_pattern, etc.)
  - compute_states convenience function
"""
from __future__ import annotations

import unittest

from scripts.triple_attribution_v0_19_45 import (
    NOT_ATTEMPTED,
    ATTEMPTED_INCOMPLETE,
    STRUCTURAL_FIXED,
    STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE,
    BEHAVIORAL_FIXED,
    compute_states,
    _attempt_pattern,
    _extract_pp_source_value,
    _new_attempt_pattern,
    _new_behavioral_fix_pattern,
    _new_structural_fix_pattern,
    _pp_state,
    _pv_state,
    _reverted_pattern,
    _structural_fix_pattern,
)


class TestPPStateDetection(unittest.TestCase):

    def test_behavioral_fixed_parameter_restored_check_and_sim_pass(self) -> None:
        text = 'parameter Real KA = 200.0 "gain";\nReal x;\nequation\nx = KA;\n'
        # With check_ok=True and simulate_ok=True -> behavioral_fixed
        self.assertEqual(_pp_state(text, "KA", text, check_ok=True, simulate_ok=True), BEHAVIORAL_FIXED)

    def test_structural_fixed_parameter_restored_check_only(self) -> None:
        text = 'parameter Real KA = 200.0 "gain";\nReal x;\nequation\nx = KA;\n'
        self.assertEqual(_pp_state(text, "KA", text, check_ok=True, simulate_ok=False), STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE)

    def test_structural_fixed_equation_with_source_value_check_only(self) -> None:
        source = 'parameter Real KA = 200.0 "gain";\n'
        text = 'Real KA;\nReal x;\nequation\nKA = 200.0;\nx = KA;\n'
        self.assertEqual(_pp_state(text, "KA", source, check_ok=True, simulate_ok=False), STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE)

    def test_attempted_incomplete_guessed_value(self) -> None:
        source = 'parameter Real KA = 200.0 "gain";\n'
        text = 'Real KA;\nReal x;\nequation\nKA = 1.0;\nx = KA;\n'
        # check_ok=False because structural balance not restored
        self.assertEqual(_pp_state(text, "KA", source, check_ok=False, simulate_ok=False), ATTEMPTED_INCOMPLETE)

    def test_attempted_incomplete_real_with_value(self) -> None:
        text = 'Real KA = 1.0 "gain";\nReal x;\nequation\nx = KA;\n'
        self.assertEqual(_pp_state(text, "KA", "", check_ok=False, simulate_ok=False), ATTEMPTED_INCOMPLETE)

    def test_not_attempted_no_action(self) -> None:
        text = 'Real KA "gain";\nReal x;\nequation\nx = KA;\n'
        self.assertEqual(_pp_state(text, "KA", "", check_ok=False, simulate_ok=False), NOT_ATTEMPTED)

    def test_extract_pp_source_value(self) -> None:
        source = 'parameter Real KA = 200.0 "gain";\n'
        self.assertEqual(_extract_pp_source_value(source, "KA"), "200.0")


class TestPVStateDetection(unittest.TestCase):

    def test_behavioral_fixed_phantom_removed_base_present(self) -> None:
        text = 'Real ETERM;\nequation\nx = ETERM;\n'
        self.assertEqual(_pv_state(text, "ETERM_phantom", "ETERM", check_ok=True, simulate_ok=True), BEHAVIORAL_FIXED)

    def test_structural_fixed_phantom_removed_check_only(self) -> None:
        text = 'Real ETERM;\n'
        self.assertEqual(_pv_state(text, "ETERM_phantom", "ETERM", check_ok=True, simulate_ok=False), STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE)

    def test_attempted_incomplete_phantom_removed_but_model_not_check_pass(self) -> None:
        text = 'Real ETERM;\n'
        self.assertEqual(_pv_state(text, "ETERM_phantom", "ETERM", check_ok=False, simulate_ok=False), ATTEMPTED_INCOMPLETE)

    def test_attempted_incomplete_bridge_equation(self) -> None:
        text = 'Real ETERM;\nReal ETERM_phantom "term voltage";\nequation\nETERM_phantom = ETERM;\nx = ETERM_phantom;\n'
        self.assertEqual(_pv_state(text, "ETERM_phantom", "ETERM", check_ok=False, simulate_ok=False), ATTEMPTED_INCOMPLETE)

    def test_attempted_incomplete_commented_decl(self) -> None:
        text = 'Real ETERM;\n// Real ETERM_phantom "term voltage";\nequation\nx = ETERM;\n'
        self.assertEqual(_pv_state(text, "ETERM_phantom", "ETERM", check_ok=False, simulate_ok=False), ATTEMPTED_INCOMPLETE)

    def test_not_attempted_phantom_still_present(self) -> None:
        text = 'Real ETERM;\nReal ETERM_phantom "term voltage";\nequation\nx = ETERM_phantom;\n'
        self.assertEqual(_pv_state(text, "ETERM_phantom", "ETERM", check_ok=False, simulate_ok=False), NOT_ATTEMPTED)


class TestPatternBuilders(unittest.TestCase):

    def test_structural_fix_pattern_pp1_only(self) -> None:
        self.assertEqual(_structural_fix_pattern([STRUCTURAL_FIXED, NOT_ATTEMPTED, NOT_ATTEMPTED]), "pp1")

    def test_structural_fix_pattern_both_pp(self) -> None:
        self.assertEqual(_structural_fix_pattern([STRUCTURAL_FIXED, STRUCTURAL_FIXED, NOT_ATTEMPTED]), "pp1_pp2")

    def test_structural_fix_pattern_all_three(self) -> None:
        self.assertEqual(_structural_fix_pattern([STRUCTURAL_FIXED, STRUCTURAL_FIXED, STRUCTURAL_FIXED]), "pp1_pp2_pv")

    def test_structural_fix_pattern_none(self) -> None:
        self.assertEqual(_structural_fix_pattern([NOT_ATTEMPTED, NOT_ATTEMPTED, NOT_ATTEMPTED]), "none")

    def test_structural_fix_pattern_includes_behavioral_fixed(self) -> None:
        self.assertEqual(_structural_fix_pattern([BEHAVIORAL_FIXED, NOT_ATTEMPTED, NOT_ATTEMPTED]), "pp1")

    def test_structural_fix_pattern_includes_behavioral_incomplete(self) -> None:
        self.assertEqual(_structural_fix_pattern([STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE, NOT_ATTEMPTED, NOT_ATTEMPTED]), "pp1")

    def test_attempt_pattern_includes_attempted_incomplete(self) -> None:
        self.assertEqual(
            _attempt_pattern([ATTEMPTED_INCOMPLETE, NOT_ATTEMPTED, STRUCTURAL_FIXED]),
            "pp1_pv",
        )

    def test_new_structural_fix_pattern_pp1_newly_structurally_fixed(self) -> None:
        prev = [NOT_ATTEMPTED, NOT_ATTEMPTED, NOT_ATTEMPTED]
        now = [STRUCTURAL_FIXED, NOT_ATTEMPTED, NOT_ATTEMPTED]
        self.assertEqual(_new_structural_fix_pattern(prev, now), "pp1")

    def test_new_behavioral_fix_pattern_pp1_newly_behaviorally_fixed(self) -> None:
        prev = [STRUCTURAL_FIXED, NOT_ATTEMPTED, NOT_ATTEMPTED]
        now = [BEHAVIORAL_FIXED, NOT_ATTEMPTED, NOT_ATTEMPTED]
        self.assertEqual(_new_behavioral_fix_pattern(prev, now), "pp1")

    def test_new_structural_not_triggered_when_only_value_changed(self) -> None:
        # PP moves from attempted_incomplete to structural_fixed
        prev = [ATTEMPTED_INCOMPLETE, NOT_ATTEMPTED, NOT_ATTEMPTED]
        now = [STRUCTURAL_FIXED, NOT_ATTEMPTED, NOT_ATTEMPTED]
        self.assertEqual(_new_structural_fix_pattern(prev, now), "pp1")

    def test_new_attempt_pattern_pp1_newly_attempted(self) -> None:
        prev = [NOT_ATTEMPTED, NOT_ATTEMPTED, NOT_ATTEMPTED]
        now = [ATTEMPTED_INCOMPLETE, NOT_ATTEMPTED, NOT_ATTEMPTED]
        self.assertEqual(_new_attempt_pattern(prev, now), "pp1")

    def test_reverted_pattern_pp1_regressed(self) -> None:
        prev = [STRUCTURAL_FIXED, STRUCTURAL_FIXED, NOT_ATTEMPTED]
        now = [ATTEMPTED_INCOMPLETE, STRUCTURAL_FIXED, NOT_ATTEMPTED]
        self.assertEqual(_reverted_pattern(prev, now), "pp1")

    def test_reverted_pattern_none(self) -> None:
        prev = [STRUCTURAL_FIXED, STRUCTURAL_FIXED, NOT_ATTEMPTED]
        now = [STRUCTURAL_FIXED, STRUCTURAL_FIXED, STRUCTURAL_FIXED]
        self.assertEqual(_reverted_pattern(prev, now), "none")


class TestComputeStates(unittest.TestCase):

    def test_all_behavioral_fixed(self) -> None:
        source = 'parameter Real KA = 200.0 "gain";\nparameter Real TR = 0.02 "tc";\nReal ETERM;\n'
        text = 'parameter Real KA = 200.0 "gain";\nparameter Real TR = 0.02 "tc";\nReal ETERM;\n'
        states = compute_states(text, "KA", "TR", "ETERM_phantom", "ETERM", source, check_ok=True, simulate_ok=True)
        self.assertEqual(states["pp1"], BEHAVIORAL_FIXED)
        self.assertEqual(states["pp2"], BEHAVIORAL_FIXED)
        self.assertEqual(states["pv"], BEHAVIORAL_FIXED)

    def test_mixed_structural_vs_behavioral(self) -> None:
        source = 'parameter Real KA = 200.0 "gain";\nparameter Real TR = 0.02 "tc";\nReal ETERM;\n'
        text = 'Real KA = 1.0;\nparameter Real TR = 0.02 "tc";\nReal ETERM;\nequation\nKA = 1.0;\n'
        states = compute_states(text, "KA", "TR", "ETERM_phantom", "ETERM", source, check_ok=True, simulate_ok=False)
        self.assertEqual(states["pp1"], STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE)
        self.assertEqual(states["pp2"], STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE)
        self.assertEqual(states["pv"], STRUCTURAL_FIXED_BEHAVIORAL_INCOMPLETE)


if __name__ == "__main__":
    unittest.main()
