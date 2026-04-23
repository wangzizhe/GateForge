from __future__ import annotations

import unittest

from gateforge.agent_modelica_omc_query_api_v1 import (
    declared_but_unused,
    extract_equation_statements,
    extract_real_declarations,
    structural_signal_summary,
    who_defines,
    who_uses,
)


SAMPLE_MODEL = """
model QueryToy
  parameter Real R = 10.0 "resistance";
  parameter Real K;
  constant Real C0 = 1.0;
  Real x(start=1.0);
  discrete Real mode;
protected
  Real hidden;
  Real unused_phantom;
equation
  der(x) = -x / R + hidden;
  hidden = K;
  y = ETERM + R1.p.v;
  connect(a.p, b.p);
end QueryToy;
"""


class TestDeclarations(unittest.TestCase):

    def test_extracts_parameter_with_binding(self) -> None:
        rows = extract_real_declarations(SAMPLE_MODEL)
        r = next(row for row in rows if row["name"] == "R")
        self.assertEqual(r["kind"], "parameter")
        self.assertTrue(r["has_binding"])

    def test_extracts_unbound_parameter(self) -> None:
        rows = extract_real_declarations(SAMPLE_MODEL)
        k = next(row for row in rows if row["name"] == "K")
        self.assertEqual(k["kind"], "parameter")
        self.assertFalse(k["has_binding"])

    def test_real_start_modifier_is_not_binding(self) -> None:
        rows = extract_real_declarations(SAMPLE_MODEL)
        x = next(row for row in rows if row["name"] == "x")
        self.assertEqual(x["kind"], "real")
        self.assertFalse(x["has_binding"])

    def test_protected_section_is_recorded(self) -> None:
        rows = extract_real_declarations(SAMPLE_MODEL)
        hidden = next(row for row in rows if row["name"] == "hidden")
        self.assertEqual(hidden["section"], "protected")


class TestEquations(unittest.TestCase):

    def test_extracts_derivative_equation(self) -> None:
        rows = extract_equation_statements(SAMPLE_MODEL)
        der = rows[0]
        self.assertEqual(der["lhs"], "der(x)")
        self.assertEqual(der["base_variable"], "x")
        self.assertTrue(der["is_derivative_lhs"])

    def test_extracts_algebraic_equation(self) -> None:
        rows = extract_equation_statements(SAMPLE_MODEL)
        hidden = rows[1]
        self.assertEqual(hidden["lhs"], "hidden")
        self.assertEqual(hidden["rhs"], "K")

    def test_extracts_connect_statement(self) -> None:
        rows = extract_equation_statements(SAMPLE_MODEL)
        conn = rows[3]
        self.assertTrue(conn["is_connect"])
        self.assertIn("connect(a.p, b.p)", conn["statement_text"])


class TestWhoDefinesUses(unittest.TestCase):

    def test_who_defines_plain_lhs(self) -> None:
        rows = who_defines(SAMPLE_MODEL, "hidden")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lhs"], "hidden")

    def test_who_defines_derivative_base_variable(self) -> None:
        rows = who_defines(SAMPLE_MODEL, "x")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lhs"], "der(x)")

    def test_who_uses_rhs_only(self) -> None:
        rows = who_uses(SAMPLE_MODEL, "hidden")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lhs"], "der(x)")

    def test_who_uses_does_not_count_lhs(self) -> None:
        rows = who_uses(SAMPLE_MODEL, "x")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lhs"], "der(x)")

    def test_who_uses_connect_textually(self) -> None:
        rows = who_uses(SAMPLE_MODEL, "a")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["is_connect"])


class TestUnusedAndSummary(unittest.TestCase):

    def test_declared_but_unused_excludes_bound_parameter(self) -> None:
        rows = declared_but_unused(SAMPLE_MODEL)
        names = {row["name"] for row in rows}
        self.assertNotIn("R", names)

    def test_declared_but_unused_excludes_unbound_parameter(self) -> None:
        rows = declared_but_unused(SAMPLE_MODEL)
        names = {row["name"] for row in rows}
        self.assertNotIn("K", names)

    def test_declared_but_unused_reports_plain_real(self) -> None:
        rows = declared_but_unused(SAMPLE_MODEL)
        names = {row["name"] for row in rows}
        self.assertIn("unused_phantom", names)

    def test_summary_reports_unbound_parameter_separately(self) -> None:
        summary = structural_signal_summary(SAMPLE_MODEL)
        names = {row["name"] for row in summary["unbound_parameters"]}
        self.assertIn("K", names)
        unused_names = {row["name"] for row in summary["declared_but_unused"]}
        self.assertNotIn("K", unused_names)

    def test_summary_reports_counts(self) -> None:
        summary = structural_signal_summary(SAMPLE_MODEL)
        self.assertEqual(summary["declaration_count"], 7)
        self.assertEqual(summary["equation_count"], 3)
        self.assertEqual(summary["connect_count"], 1)

    def test_summary_keeps_uppercase_used_but_undeclared(self) -> None:
        summary = structural_signal_summary(SAMPLE_MODEL)
        names = {row["name"] for row in summary["used_but_undeclared"]}
        self.assertIn("ETERM", names)

    def test_summary_uses_dotted_reference_roots(self) -> None:
        summary = structural_signal_summary(SAMPLE_MODEL)
        names = {row["name"] for row in summary["used_but_undeclared"]}
        self.assertIn("R1", names)
        self.assertNotIn("p", names)
        self.assertNotIn("v", names)


if __name__ == "__main__":
    unittest.main()
