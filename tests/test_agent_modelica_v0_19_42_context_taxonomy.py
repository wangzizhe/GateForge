from __future__ import annotations

import unittest

from scripts.build_failure_taxonomy_v0_19_42 import (
    _parameter_fixed,
    _phantom_fixed,
    _taxonomy_for_failure,
)
from scripts.run_context_ablation_experiment_v0_19_42 import (
    _dm_generic_hint_context,
    _dm_root_only_context,
)


class TestV01942ContextTaxonomy(unittest.TestCase):
    def test_dm_root_only_context_strips_fix_lines(self):
        text = """model M
Real x;
Real y;
equation
y = x;
end M;
"""
        ctx = _dm_root_only_context(text)
        self.assertIn("Root cause variables:", ctx)
        self.assertNotIn("Fix:", ctx)

    def test_dm_generic_hint_context_adds_single_fix_line(self):
        text = """model M
Real x;
Real y;
equation
y = x;
end M;
"""
        ctx = _dm_generic_hint_context(text)
        self.assertIn("generic fix hint", ctx.lower())
        self.assertIn("Fix:", ctx)

    def test_parameter_fixed_detects_parameter_restore(self):
        patched = 'model M\nparameter Real KA = 10;\nequation\nx = KA;\nend M;\n'
        self.assertTrue(_parameter_fixed(patched, "KA"))

    def test_phantom_fixed_detects_removed_declaration(self):
        patched = 'model M\nReal ETERM;\nequation\nx = ETERM;\nend M;\n'
        self.assertTrue(_phantom_fixed(patched, "ETERM_phantom"))

    def test_taxonomy_detects_noop(self):
        case = {"mutation_type": "compound_underdetermined", "pp_target": "KA", "pv_target": "ETERM_phantom"}
        result = {"fix_pass": False, "error_class": "", "llm_error": "", "omc_output_snippet": ""}
        broken = "broken"
        self.assertEqual(_taxonomy_for_failure(case, "condition_c2", result, broken, broken), "NO_OP_AMBIGUITY")

    def test_taxonomy_detects_execution_incomplete_for_phantom(self):
        case = {"mutation_type": "phantom_variable", "target_name": "ETERM_phantom"}
        result = {"fix_pass": False, "error_class": "", "llm_error": "", "omc_output_snippet": ""}
        broken = 'model M\nReal ETERM_phantom;\nequation\nx = ETERM_phantom;\nend M;\n'
        patched = 'model M\nReal ETERM_phantom;\nequation\nx = ETERM;\nend M;\n'
        self.assertEqual(_taxonomy_for_failure(case, "condition_c3", result, patched, broken), "EXECUTION_INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
