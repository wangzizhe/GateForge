from __future__ import annotations

import unittest

from scripts.analyze_compound_turn_attribution_v0_19_44 import (
    _new_fix_pattern,
    _parameter_fixed,
    _phantom_fixed,
    _reverted_pattern,
)


class TestV01944CompoundTurnAttribution(unittest.TestCase):
    def test_parameter_fixed_detects_parameter_restore(self) -> None:
        text = "parameter Real KA = 20.0;\nReal x;\nequation\nx = KA;\n"
        self.assertTrue(_parameter_fixed(text, "KA"))

    def test_parameter_fixed_detects_equation_restore(self) -> None:
        text = "Real KA;\nReal x;\nequation\nKA = 20.0;\nx = KA;\n"
        self.assertTrue(_parameter_fixed(text, "KA"))

    def test_phantom_fixed_requires_decl_removed_and_base_present(self) -> None:
        text = "Real ETERM;\nequation\nx = ETERM;\n"
        self.assertTrue(_phantom_fixed(text, "ETERM_phantom", "ETERM"))
        broken = "Real ETERM_phantom;\nequation\nx = ETERM_phantom;\n"
        self.assertFalse(_phantom_fixed(broken, "ETERM_phantom", "ETERM"))

    def test_new_fix_pattern(self) -> None:
        self.assertEqual(_new_fix_pattern(False, False, True, False), "pp_only")
        self.assertEqual(_new_fix_pattern(False, False, False, True), "pv_only")
        self.assertEqual(_new_fix_pattern(False, False, True, True), "both")
        self.assertEqual(_new_fix_pattern(True, False, True, False), "none")

    def test_reverted_pattern(self) -> None:
        self.assertEqual(_reverted_pattern(True, True, False, True), "pp_only")
        self.assertEqual(_reverted_pattern(True, True, True, False), "pv_only")
        self.assertEqual(_reverted_pattern(True, True, False, False), "both")
        self.assertEqual(_reverted_pattern(False, True, False, True), "none")


if __name__ == "__main__":
    unittest.main()
