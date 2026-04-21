"""Unit tests for triple underdetermined mutation building (v0.19.45).

Verifies that applying PP1 + PP2 + PV simultaneously produces the expected
structural changes and that the three root causes are distinct.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_triple_underdetermined_mutations_v0_19_45 import (
    PPSpec,
    PVSpec,
    EquationStatement,
    _apply_pp_pp_pv,
    _collect_pp_specs,
    _collect_pv_specs,
    _parse_equation_section,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

# Source model with two promotable parameters (KA, TR) and two phantomable variables (VERR, ETERM)
_SIMPLE_SOURCE = """\
model SimpleAVR
  parameter Real KA = 200.0  "voltage regulator gain";
  parameter Real TR = 0.02   "measurement time constant";
  Real VM(start = 1.02)  "measured voltage";
  Real VERR  "voltage error";
  Real ETERM  "terminal voltage";
  Real AUX  "auxiliary";
equation
  ETERM = 1.02;
  VERR = 1.05 - VM;
  AUX = VERR + 1.0;
  der(VM) = (ETERM - VM) / TR;
end SimpleAVR;
"""


class TestCollectPPSpecs(unittest.TestCase):

    def test_finds_promotable_parameters(self) -> None:
        lines = _SIMPLE_SOURCE.splitlines()
        specs = _collect_pp_specs(lines)
        names = [s.var_name for s in specs]
        self.assertIn("KA", names)
        self.assertIn("TR", names)

    def test_pp_spec_new_line_is_real_not_parameter(self) -> None:
        lines = _SIMPLE_SOURCE.splitlines()
        specs = _collect_pp_specs(lines)
        tr_spec = next(s for s in specs if s.var_name == "TR")
        self.assertIn("Real TR", tr_spec.new_line)
        self.assertNotIn("parameter", tr_spec.new_line)


class TestCollectPVSpecs(unittest.TestCase):

    def test_finds_phantomable_algebraics(self) -> None:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        specs = _collect_pv_specs(lines, equations)
        names = [s.var_name for s in specs]
        # VERR appears in der(VM) equation as non-LHS
        # ETERM appears in VERR equation as non-LHS
        self.assertIn("VERR", names)
        self.assertIn("ETERM", names)

    def test_pv_spec_phantom_name_suffix(self) -> None:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        specs = _collect_pv_specs(lines, equations)
        for s in specs:
            self.assertEqual(s.phantom_name, f"{s.var_name}_phantom")


class TestApplyTriplePPPPV(unittest.TestCase):

    def _get_triple_text(self, pp1_var: str = "KA", pp2_var: str = "TR", pv_var: str = "VERR") -> str:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)
        pp1 = next(s for s in pp_specs if s.var_name == pp1_var)
        pp2 = next(s for s in pp_specs if s.var_name == pp2_var)
        pv = next(s for s in pv_specs if s.var_name == pv_var)
        return _apply_pp_pp_pv(lines, pp1, pp2, pv)

    def test_parameters_no_longer_present(self) -> None:
        triple = self._get_triple_text()
        self.assertNotIn("parameter Real KA", triple)
        self.assertNotIn("parameter Real TR", triple)

    def test_promoted_variables_present(self) -> None:
        triple = self._get_triple_text()
        self.assertIn("Real KA", triple)
        self.assertIn("Real TR", triple)

    def test_phantom_declaration_inserted(self) -> None:
        triple = self._get_triple_text()
        self.assertIn("Real VERR_phantom", triple)

    def test_original_var_still_has_own_declaration(self) -> None:
        triple = self._get_triple_text()
        lines = triple.splitlines()
        decl_lines = [l for l in lines if 'Real VERR' in l]
        # Should have both original VERR and VERR_phantom
        self.assertTrue(len(decl_lines) >= 2)

    def test_equation_reference_substituted(self) -> None:
        triple = self._get_triple_text()
        # VERR appears as RHS in AUX = VERR + 1.0; should become AUX = VERR_phantom + 1.0;
        self.assertIn("AUX = VERR_phantom + 1.0", triple)

    def test_untouched_equation_stays_same(self) -> None:
        triple = self._get_triple_text()
        # ETERM = 1.02; should be unchanged
        self.assertIn("ETERM = 1.02", triple)

    def test_triple_model_line_count(self) -> None:
        original_count = len(_SIMPLE_SOURCE.splitlines())
        triple = self._get_triple_text()
        triple_count = len(triple.splitlines())
        # +1 for phantom declaration, PP replacements don't change count
        self.assertEqual(triple_count, original_count + 1)

    def test_three_root_causes_distinct(self) -> None:
        triple = self._get_triple_text()
        # KA, TR, VERR should all be distinct variables affected
        self.assertIn("Real KA", triple)
        self.assertIn("Real TR", triple)
        self.assertIn("Real VERR_phantom", triple)

    def test_pp_vars_not_also_pv_targets(self) -> None:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)
        # Ensure no overlap between PP targets and PV base vars
        pp_names = {s.var_name for s in pp_specs}
        pv_names = {s.var_name for s in pv_specs}
        overlap = pp_names & pv_names
        # VM has start= so it's not in PV specs; overlap should be empty
        self.assertEqual(overlap, set())


class TestTripleCombinations(unittest.TestCase):

    def test_all_distinct_combinations_possible(self) -> None:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)

        # Count valid PP+PP+PV triples where all three targets are distinct
        valid_count = 0
        from itertools import combinations
        for pp1, pp2 in combinations(pp_specs, 2):
            for pv in pv_specs:
                if pv.var_name not in {pp1.var_name, pp2.var_name}:
                    valid_count += 1

        # 2 PP specs, choose 2 = 1 pair; 3 PV specs (VERR, ETERM, AUX but AUX has no non-LHS use)
        # Actually AUX = VERR + 1.0 means AUX is LHS, VERR is RHS → VERR is PV candidate
        # ETERM is in der(VM) RHS → ETERM is PV candidate
        # AUX is only LHS → AUX is NOT PV candidate
        # So 2 PV candidates (VERR, ETERM), choose any 1 for PV = 2 valid triples
        self.assertEqual(valid_count, 2)


if __name__ == "__main__":
    unittest.main()
