from __future__ import annotations

import unittest
from pathlib import Path

from scripts.build_equation_deletion_mutations_v0_19_33 import (
    OPENIPSL_LIBRARY_ROOT,
    SourceSpec,
    _classify_failure,
    _delete_equation,
    _extract_qualified_model_name,
    _infer_library_model_path,
    _parse_equation_section,
)


GENROE_PATH = (
    Path("assets_private/agent_modelica_cross_domain_openipsl_v1_fixture_v1/source_models/GENROE_12c13f38c4.mo").resolve()
)


class TestV01933EquationDeletion(unittest.TestCase):
    def test_extract_qualified_model_name(self):
        text = "within OpenIPSL.Electrical.Machines.PSSE;\nmodel GENROE\nend GENROE;\n"
        self.assertEqual(
            _extract_qualified_model_name(text),
            "OpenIPSL.Electrical.Machines.PSSE.GENROE",
        )

    def test_infer_library_model_path(self):
        path = _infer_library_model_path(
            OPENIPSL_LIBRARY_ROOT,
            "OpenIPSL.Electrical.Machines.PSSE.GENROE",
        )
        self.assertEqual(
            path,
            OPENIPSL_LIBRARY_ROOT / "Electrical" / "Machines" / "PSSE" / "GENROE.mo",
        )

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

    def test_parse_equation_section_finds_der_equations(self):
        if not GENROE_PATH.exists():
            self.skipTest("GENROE source model not available")
        text = GENROE_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        equations = _parse_equation_section(lines)
        eq_texts = [eq.text for eq in equations]
        der_eqs = [eq for eq in equations if eq.is_der]
        self.assertGreater(len(der_eqs), 0, "should find at least one der() equation")
        der_vars = {eq.lhs_variable for eq in der_eqs}
        self.assertIn("Epq", der_vars)
        self.assertIn("Epd", der_vars)

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
        from scripts.build_equation_deletion_mutations_v0_19_33 import EquationStatement
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

    def test_parse_equation_section_all_genroe_equations(self):
        if not GENROE_PATH.exists():
            self.skipTest("GENROE source model not available")
        text = GENROE_PATH.read_text(encoding="utf-8")
        lines = text.splitlines()
        equations = _parse_equation_section(lines)
        self.assertGreaterEqual(len(equations), 14, "GENROE should have at least 14 explicit equations")
        lhs_vars = {eq.lhs_variable for eq in equations}
        for expected in ("PSId", "PSIq", "PSIppd", "PSIpp", "XadIfd", "XaqIlq", "ud", "uq"):
            self.assertIn(expected, lhs_vars, f"expected {expected} in parsed equations")


if __name__ == "__main__":
    unittest.main()
