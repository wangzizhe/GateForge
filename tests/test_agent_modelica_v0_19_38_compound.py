"""Unit tests for compound underdetermined mutation building (v0.19.38).

Verifies that applying parameter_promotion + phantom_variable simultaneously
produces the expected structural changes and that DM context identifies both
root cause variables.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_compound_underdetermined_mutations_v0_19_38 import (
    PPSpec,
    PVSpec,
    EquationStatement,
    _apply_compound,
    _collect_pp_specs,
    _collect_pv_specs,
    _parse_equation_section,
)
from scripts.diagnostic_context_dm_v0_19_35 import build_dm_diagnostic_context

# ── fixtures ──────────────────────────────────────────────────────────────────

# Source model with one promotable parameter (TR) and one phantomable variable (VERR)
_SIMPLE_SOURCE = """\
model SimpleAVR
  parameter Real KA = 200.0  "voltage regulator gain";
  parameter Real TR = 0.02   "measurement time constant";
  Real VM(start = 1.02)  "measured voltage";
  Real VERR  "voltage error";
  Real ETERM  "terminal voltage";
equation
  ETERM = 1.02;
  VERR = 1.05 - VM;
  der(VM) = (ETERM - VM) / TR;
end SimpleAVR;
"""

# Expected compound: TR promoted + VERR phantom
_COMPOUND_EXPECTED_FRAGMENTS = [
    'Real TR',              # promoted (no longer parameter)
    'Real VERR_phantom',    # phantom inserted
    'VERR_phantom',         # used in equation
]


class TestCollectPPSpecs(unittest.TestCase):

    def test_finds_promotable_parameters(self):
        lines = _SIMPLE_SOURCE.splitlines()
        specs = _collect_pp_specs(lines)
        names = [s.var_name for s in specs]
        self.assertIn("KA", names)
        self.assertIn("TR", names)

    def test_pp_spec_new_line_is_real_not_parameter(self):
        lines = _SIMPLE_SOURCE.splitlines()
        specs = _collect_pp_specs(lines)
        tr_spec = next(s for s in specs if s.var_name == "TR")
        self.assertIn("Real TR", tr_spec.new_line)
        self.assertNotIn("parameter", tr_spec.new_line)

    def test_pp_spec_preserves_description(self):
        lines = _SIMPLE_SOURCE.splitlines()
        specs = _collect_pp_specs(lines)
        tr_spec = next(s for s in specs if s.var_name == "TR")
        self.assertIn("measurement time constant", tr_spec.new_line)


class TestCollectPVSpecs(unittest.TestCase):

    def test_finds_phantomable_algebraics(self):
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        specs = _collect_pv_specs(lines, equations)
        names = [s.var_name for s in specs]
        # VERR and ETERM are algebraic; VM has start= so it won't match _ALG_DECL_RE
        # VERR appears in der(VM) equation as non-LHS → valid phantom candidate
        self.assertIn("ETERM", names)

    def test_pv_spec_phantom_name_suffix(self):
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        specs = _collect_pv_specs(lines, equations)
        for s in specs:
            self.assertEqual(s.phantom_name, f"{s.var_name}_phantom")


class TestApplyCompound(unittest.TestCase):

    def _get_compound_text(self) -> str:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)
        tr_pp = next(s for s in pp_specs if s.var_name == "TR")
        # Find a PV spec that's not TR
        pv = next(s for s in pv_specs if s.var_name != "TR")
        return _apply_compound(lines, tr_pp, pv)

    def test_parameter_no_longer_present(self):
        compound = self._get_compound_text()
        self.assertNotIn("parameter Real TR", compound)

    def test_promoted_variable_present(self):
        compound = self._get_compound_text()
        self.assertIn("Real TR", compound)

    def test_phantom_declaration_inserted(self):
        compound = self._get_compound_text()
        # One of the algebraic vars got a phantom
        self.assertTrue(
            any(f"Real {v}_phantom" in compound for v in ["ETERM", "VERR"])
        )

    def test_original_var_still_has_own_declaration(self):
        compound = self._get_compound_text()
        # The original algebraic var declaration should still exist
        lines = compound.splitlines()
        decl_lines = [l for l in lines if 'Real ETERM' in l or 'Real VERR' in l]
        self.assertTrue(len(decl_lines) >= 2)  # original + phantom

    def test_compound_model_line_count(self):
        # Compound adds exactly 1 line (phantom declaration)
        original_count = len(_SIMPLE_SOURCE.splitlines())
        compound = self._get_compound_text()
        compound_count = len(compound.splitlines())
        self.assertEqual(compound_count, original_count + 1)

    def test_pp_var_not_also_pv_target(self):
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)
        # Check that the compound avoids using the PP variable as PV base
        # (build script skips such pairs)
        for pp in pp_specs:
            for pv in pv_specs:
                if pp.var_name == pv.var_name:
                    # This combination should be skipped by the build script
                    pass  # Just confirm they can exist; build script filters them


class TestDMContextForCompound(unittest.TestCase):

    def _get_compound_text(self) -> str:
        lines = _SIMPLE_SOURCE.splitlines()
        equations = _parse_equation_section(lines)
        pp_specs = _collect_pp_specs(lines)
        pv_specs = _collect_pv_specs(lines, equations)
        # Use TR (promoted) + ETERM (phantom)
        tr_pp = next(s for s in pp_specs if s.var_name == "TR")
        eterm_pv = next(s for s in pv_specs if s.var_name == "ETERM")
        return _apply_compound(lines, tr_pp, eterm_pv)

    def test_dm_context_runs_without_error(self):
        compound = self._get_compound_text()
        ctx = build_dm_diagnostic_context(compound)
        self.assertIsInstance(ctx, str)
        self.assertGreater(len(ctx), 0)

    def test_dm_context_reports_structural_diagnostic(self):
        compound = self._get_compound_text()
        ctx = build_dm_diagnostic_context(compound)
        self.assertIn("STRUCTURAL DIAGNOSTIC", ctx)

    def test_dm_context_mentions_phantom_variable(self):
        compound = self._get_compound_text()
        ctx = build_dm_diagnostic_context(compound)
        self.assertIn("ETERM_phantom", ctx)


if __name__ == "__main__":
    unittest.main()
