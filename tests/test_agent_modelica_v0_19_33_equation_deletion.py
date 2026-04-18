from __future__ import annotations

import unittest
from pathlib import Path

from scripts.build_equation_deletion_mutations_v0_19_33 import (
    STANDALONE_SOURCE_DIR,
    EquationStatement,
    _classify_failure,
    _delete_equation,
    _parse_equation_section,
)

SYNC_MACHINE_PATH = (
    STANDALONE_SOURCE_DIR / "SyncMachineSimplified_v0.mo"
)
THERMAL_PATH = (
    STANDALONE_SOURCE_DIR / "ThermalZone_v0.mo"
)


class TestV01933EquationDeletion(unittest.TestCase):
    def test_classify_failure_underdetermined(self):
        self.assertEqual(
            _classify_failure("Variable Epq is not determined by any equation."),
            "underdetermined_structural",
        )
        self.assertEqual(
            _classify_failure("Singular system detected in model."),
            "underdetermined_structural",
        )

    def test_classify_failure_not_found(self):
        self.assertEqual(
            _classify_failure("Class R1 not found in scope."),
            "not_found_declaration",
        )

    def test_classify_failure_other(self):
        self.assertEqual(
            _classify_failure("Some other error occurred."),
            "model_check_error_other",
        )

    def test_parse_equation_section_skips_connect(self):
        lines = [
            "equation",
            "  connect(a.p, b.n);",
            "  der(x) = 1.0;",
            "end M;",
        ]
        equations = _parse_equation_section(lines)
        self.assertEqual(len(equations), 1)
        self.assertEqual(equations[0].lhs_variable, "x")

    def test_parse_equation_section_skips_initial_equation(self):
        lines = [
            "initial equation",
            "  der(x) = 0;",
            "equation",
            "  der(x) = alpha;",
            "end M;",
        ]
        equations = _parse_equation_section(lines)
        self.assertEqual(len(equations), 1)
        self.assertEqual(equations[0].text.strip(), "der(x) = alpha;")

    def test_parse_equation_section_handles_multiline(self):
        lines = [
            "equation",
            "  XadIfd = K1d*(Epq - PSIkd) +",
            "    SE_exp(PSIpp, S10);",
            "end M;",
        ]
        equations = _parse_equation_section(lines)
        self.assertEqual(len(equations), 1)
        self.assertEqual(equations[0].lhs_variable, "XadIfd")
        self.assertFalse(equations[0].is_der)

    def test_delete_equation_removes_target_lines(self):
        lines = ["line1", "  der(x) = 1.0;", "  y = 2.0;", "end M;"]
        eq = EquationStatement(
            start_line_index=1,
            end_line_index=1,
            text="  der(x) = 1.0;",
            is_der=True,
            lhs_variable="x",
        )
        result = _delete_equation(lines, eq)
        self.assertNotIn("der(x) = 1.0;", result)
        self.assertIn("y = 2.0;", result)

    def test_parse_sync_machine_finds_der_equations(self):
        if not SYNC_MACHINE_PATH.exists():
            self.skipTest("SyncMachineSimplified_v0.mo not available")
        text = SYNC_MACHINE_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        equations = _parse_equation_section(lines)
        der_eqs = [eq for eq in equations if eq.is_der]
        self.assertGreaterEqual(len(der_eqs), 4)
        der_vars = {eq.lhs_variable for eq in der_eqs}
        for expected in ("Epq", "Epd", "PSIkd", "PSIkq"):
            self.assertIn(expected, der_vars)

    def test_parse_sync_machine_equation_count(self):
        if not SYNC_MACHINE_PATH.exists():
            self.skipTest("SyncMachineSimplified_v0.mo not available")
        text = SYNC_MACHINE_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        equations = _parse_equation_section(lines)
        self.assertEqual(len(equations), 14)

    def test_parse_thermal_zone_equation_count(self):
        if not THERMAL_PATH.exists():
            self.skipTest("ThermalZone_v0.mo not available")
        text = THERMAL_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        equations = _parse_equation_section(lines)
        self.assertEqual(len(equations), 8)

    def test_parse_thermal_zone_finds_algebraic_and_der(self):
        if not THERMAL_PATH.exists():
            self.skipTest("ThermalZone_v0.mo not available")
        text = THERMAL_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        equations = _parse_equation_section(lines)
        der_vars = {eq.lhs_variable for eq in equations if eq.is_der}
        alg_vars = {eq.lhs_variable for eq in equations if not eq.is_der}
        for v in ("T1", "T2", "T3", "Tw"):
            self.assertIn(v, der_vars)
        for v in ("Phi1", "Phi2", "Phi3", "PhiW"):
            self.assertIn(v, alg_vars)


if __name__ == "__main__":
    unittest.main()
