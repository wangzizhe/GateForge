from __future__ import annotations

import unittest
from pathlib import Path

from scripts.diagnostic_context_v0_19_34 import (
    _extract_underdetermined_variable_names,
    _find_variable_description,
    _find_equations_referencing,
    build_diagnostic_context,
)
from scripts.build_structural_mutation_experiment_v0_19_34 import (
    STANDALONE_SOURCE_DIR,
    _collect_type_b_mutations,
    _collect_type_c_mutations,
    _parse_equation_section,
)

THERMAL_PATH = STANDALONE_SOURCE_DIR / "ThermalZone_v0.mo"
SYNC_PATH = STANDALONE_SOURCE_DIR / "SyncMachineSimplified_v0.mo"


# ── diagnostic_context_v0_19_34 ──────────────────────────────────────────────

class TestExtractUnderdeterminedVariableNames(unittest.TestCase):
    def test_standard_omc_message(self):
        err = "Variable Phi1 is not determined by any equation."
        self.assertEqual(_extract_underdetermined_variable_names(err), ["Phi1"])

    def test_multiple_variables(self):
        err = (
            "Variable Epq is not determined by any equation.\n"
            "Variable XadIfd is not determined by any equation.\n"
        )
        names = _extract_underdetermined_variable_names(err)
        self.assertIn("Epq", names)
        self.assertIn("XadIfd", names)

    def test_no_match_returns_empty(self):
        err = "Singular system detected in model."
        self.assertEqual(_extract_underdetermined_variable_names(err), [])

    def test_deduplication(self):
        err = "Variable Tpd0 is not determined.\nVariable Tpd0 is not determined.\n"
        self.assertEqual(_extract_underdetermined_variable_names(err), ["Tpd0"])


class TestFindVariableDescription(unittest.TestCase):
    _MODEL = (
        "model M\n"
        '  parameter Real Tpd0 = 5.0 "d-axis transient time constant";\n'
        '  Real Phi1  "net heat flux into zone 1";\n'
        "equation\n"
        "  Phi1 = 1.0;\n"
        "end M;\n"
    )

    def test_parameter_with_description(self):
        self.assertEqual(
            _find_variable_description(self._MODEL, "Tpd0"),
            "d-axis transient time constant",
        )

    def test_algebraic_with_description(self):
        self.assertEqual(
            _find_variable_description(self._MODEL, "Phi1"),
            "net heat flux into zone 1",
        )

    def test_missing_variable_returns_empty(self):
        self.assertEqual(_find_variable_description(self._MODEL, "NoSuch"), "")


class TestFindEquationsReferencing(unittest.TestCase):
    _MODEL = (
        "model M\n"
        '  Real Phi1 "flux";\n'
        '  Real T1(start=293.0) "temperature";\n'
        "equation\n"
        "  Phi1 = 100.0 - 5.0 * T1;\n"
        "  der(T1) = Phi1 / 2.5e6;\n"
        "end M;\n"
    )

    def test_finds_defining_and_use_equations(self):
        eqs = _find_equations_referencing(self._MODEL, "Phi1")
        self.assertEqual(len(eqs), 2)

    def test_finds_only_relevant(self):
        eqs = _find_equations_referencing(self._MODEL, "T1")
        texts = " ".join(eqs)
        self.assertIn("T1", texts)

    def test_returns_empty_for_unknown_var(self):
        self.assertEqual(_find_equations_referencing(self._MODEL, "NoSuch"), [])


class TestBuildDiagnosticContext(unittest.TestCase):
    _MODEL = (
        "model M\n"
        '  Real Phi1_phantom "net heat flux";\n'
        "equation\n"
        "  der(T1) = Phi1_phantom / C1;\n"
        "end M;\n"
    )

    def test_includes_variable_name(self):
        err = "Variable Phi1_phantom is not determined by any equation."
        ctx = build_diagnostic_context(self._MODEL, err)
        self.assertIn("Phi1_phantom", ctx)

    def test_includes_description(self):
        err = "Variable Phi1_phantom is not determined by any equation."
        ctx = build_diagnostic_context(self._MODEL, err)
        self.assertIn("net heat flux", ctx)

    def test_includes_equation(self):
        err = "Variable Phi1_phantom is not determined by any equation."
        ctx = build_diagnostic_context(self._MODEL, err)
        self.assertIn("der(T1)", ctx)

    def test_fallback_when_no_variable_identified(self):
        err = "Singular system detected."
        ctx = build_diagnostic_context(self._MODEL, err)
        self.assertIn("Structural error", ctx)


# ── build_structural_mutation_experiment_v0_19_34 ────────────────────────────

class TestCollectTypeBMutations(unittest.TestCase):
    def test_promotes_parameter_with_description(self):
        lines = [
            "model M",
            '  parameter Real Tpd0 = 5.0  "d-axis transient time constant";',
            "equation",
            "  der(x) = Tpd0;",
            "end M;",
        ]
        results = _collect_type_b_mutations(lines)
        names = [r[0] for r in results]
        self.assertIn("Tpd0", names)

    def test_skips_parameter_without_description(self):
        lines = [
            "model M",
            "  parameter Real K3d = 0.5;",
            "equation",
            "  x = K3d;",
            "end M;",
        ]
        results = _collect_type_b_mutations(lines)
        self.assertEqual(results, [])

    def test_promoted_line_has_no_parameter_keyword(self):
        lines = [
            "model M",
            '  parameter Real TA = 0.06 "voltage regulator time constant";',
            "end M;",
        ]
        results = _collect_type_b_mutations(lines)
        self.assertEqual(len(results), 1)
        _, _, mutated_text = results[0]
        # promoted line should not contain "parameter"
        for line in mutated_text.splitlines():
            if "TA" in line and "Real" in line:
                self.assertNotIn("parameter", line)
                self.assertNotIn("= 0.06", line)
                break


class TestCollectTypeCMutations(unittest.TestCase):
    def test_creates_phantom_for_algebraic_var(self):
        lines = [
            "model M",
            '  Real Phi1 "net heat flux";',
            "equation",
            "  Phi1 = 100.0;",
            "  der(T1) = Phi1 / C1;",
            "end M;",
        ]
        equations = _parse_equation_section(lines)
        results = _collect_type_c_mutations(lines)
        phantom_names = [r[0] for r in results]
        self.assertIn("Phi1_phantom", phantom_names)

    def test_phantom_uses_original_description(self):
        lines = [
            "model M",
            '  Real VERR "voltage error signal";',
            "equation",
            "  VERR = 1.0 - VM;",
            "  der(VR) = VERR / TA;",
            "end M;",
        ]
        results = _collect_type_c_mutations(lines)
        self.assertTrue(len(results) >= 1)
        phantom_name, description, _ = results[0]
        self.assertEqual(phantom_name, "VERR_phantom")
        self.assertEqual(description, "voltage error signal")

    def test_phantom_appears_in_mutated_use_equation(self):
        lines = [
            "model M",
            '  Real Phi1 "flux";',
            "equation",
            "  Phi1 = 100.0;",
            "  der(T1) = Phi1 / C1;",
            "end M;",
        ]
        results = _collect_type_c_mutations(lines)
        self.assertTrue(len(results) >= 1)
        _, _, mutated_text = results[0]
        self.assertIn("Phi1_phantom", mutated_text)
        # Original use equation should now reference phantom
        self.assertIn("Phi1_phantom / C1", mutated_text)
        # Defining equation should still reference original Phi1
        self.assertIn("Phi1 = 100.0", mutated_text)


# ── file-dependent tests ──────────────────────────────────────────────────────

class TestTypeBOnRealModels(unittest.TestCase):
    def test_thermal_zone_has_promotable_parameters(self):
        if not THERMAL_PATH.exists():
            self.skipTest("ThermalZone_v0.mo not available")
        lines = THERMAL_PATH.read_text(encoding="utf-8").splitlines()
        results = _collect_type_b_mutations(lines)
        names = [r[0] for r in results]
        self.assertIn("C1", names)
        self.assertIn("H12", names)

    def test_sync_machine_has_promotable_parameters(self):
        if not SYNC_PATH.exists():
            self.skipTest("SyncMachineSimplified_v0.mo not available")
        lines = SYNC_PATH.read_text(encoding="utf-8").splitlines()
        results = _collect_type_b_mutations(lines)
        names = [r[0] for r in results]
        self.assertIn("Tpd0", names)
        self.assertIn("Tpq0", names)


class TestTypeCOnRealModels(unittest.TestCase):
    def test_thermal_zone_has_phantom_candidates(self):
        if not THERMAL_PATH.exists():
            self.skipTest("ThermalZone_v0.mo not available")
        lines = THERMAL_PATH.read_text(encoding="utf-8").splitlines()
        results = _collect_type_c_mutations(lines)
        phantom_names = [r[0] for r in results]
        self.assertIn("Phi1_phantom", phantom_names)

    def test_sync_machine_has_phantom_candidates(self):
        if not SYNC_PATH.exists():
            self.skipTest("SyncMachineSimplified_v0.mo not available")
        lines = SYNC_PATH.read_text(encoding="utf-8").splitlines()
        results = _collect_type_c_mutations(lines)
        phantom_names = [r[0] for r in results]
        # PSIppd, PSId, etc. should be candidates
        self.assertTrue(len(results) >= 2)


class TestDiagnosticContextOnRealModels(unittest.TestCase):
    def test_thermal_zone_phi1_phantom(self):
        if not THERMAL_PATH.exists():
            self.skipTest("ThermalZone_v0.mo not available")
        text = THERMAL_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        mutations = _collect_type_c_mutations(lines)
        self.assertTrue(len(mutations) >= 1)
        phantom_name, description, mutated_text = mutations[0]

        omc_error = f"Variable {phantom_name} is not determined by any equation."
        ctx = build_diagnostic_context(mutated_text, omc_error)

        self.assertIn(phantom_name, ctx)
        self.assertIn(description, ctx)
        # Should find at least one equation referencing the phantom
        self.assertNotIn("(none found", ctx)


if __name__ == "__main__":
    unittest.main()
