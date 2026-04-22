"""Unit tests for OMC diagnostic formatter (v0.19.48).

Covers:
  - Equation/variable count extraction
  - Trivial equation count extraction
  - Undersolved variable parsing
  - Main error extraction
  - Full formatting output
  - Information completeness (round-trip)
  - Noise reduction metrics
"""
from __future__ import annotations

import unittest

from gateforge.omc_diagnostic_formatter_v0_19_48 import (
    _extract_eq_var_counts,
    _extract_main_error,
    _extract_trivial_eq_count,
    _extract_undersolved_variables,
    format_omc_error_excerpt,
    format_omc_error_excerpt_compact,
)


SAMPLE_OMC_OUTPUT = '''true
true
"Check of TestModel completed successfully.
Class TestModel has 14 equation(s) and 17 variable(s).
3 of these are trivial equation(s)."
record SimulationResult
    resultFile = "",
    simulationOptions = "startTime = 0.0, stopTime = 0.05",
    messages = "Failed to build model: TestModel",
    timeFrontend = 0.0,
    timeBackend = 0.0,
    timeSimCode = 0.0,
    timeTemplates = 0.0,
    timeCompile = 0.0,
    timeSimulation = 0.0,
    timeTotal = 0.0
end SimulationResult;
"Error: Too few equations, under-determined system. The model has 14 equation(s) and 17 variable(s).
[/workspace/TestModel.mo:42:3-42:51:writable] Warning: Variable PSIppq_phantom does not have any remaining equation to be solved in.
  The original equations were:
  Equation 10: PSIpp = sqrt(PSIppd ^ 2.0 + PSIppq_phantom ^ 2.0), which needs to solve for PSIpp
[/workspace/TestModel.mo:46:3-46:44:writable] Warning: Variable XadIfd does not have any remaining equation to be solved in.
  The original equations were:
  Equation 13: XadIfd = Epq + id * (Xd - Xpd), which needs to solve for id
  Equation 4: der(Epq) = (EFD - XadIfd) / Tpd0, which needs to solve for EFD
[/workspace/TestModel.mo:34:3-34:49:writable] Warning: Variable Epq does not have any remaining equation to be solved in.
  The original equations were:
  Equation 13: XadIfd = Epq + id * (Xd - Xpd), which needs to solve for id
  Equation 8: PSIppd = Epq * K3d + PSIkd * K4d, which needs to solve for PSIppd
  Equation 6: der(PSIkd) = (Epq + (Xl - Xpd) * id - PSIkd) / Tppd0, which needs to solve for PSIkd
  Equation 4: der(Epq) = (EFD - XadIfd) / Tpd0, which needs to solve for EFD
"'''


class TestExtractEqVarCounts(unittest.TestCase):

    def test_parses_standard_omc(self) -> None:
        eq, var = _extract_eq_var_counts(SAMPLE_OMC_OUTPUT)
        self.assertEqual(eq, 14)
        self.assertEqual(var, 17)

    def test_returns_none_when_no_match(self) -> None:
        eq, var = _extract_eq_var_counts("some random text")
        self.assertIsNone(eq)
        self.assertIsNone(var)


class TestExtractTrivialEqCount(unittest.TestCase):

    def test_parses_trivial_count(self) -> None:
        count = _extract_trivial_eq_count(SAMPLE_OMC_OUTPUT)
        self.assertEqual(count, 3)

    def test_returns_none_when_no_match(self) -> None:
        count = _extract_trivial_eq_count("has 5 equations")
        self.assertIsNone(count)


class TestExtractUndersolvedVariables(unittest.TestCase):

    def test_parses_all_three_variables(self) -> None:
        vars_list = _extract_undersolved_variables(SAMPLE_OMC_OUTPUT)
        self.assertEqual(len(vars_list), 3)
        names = [v.name for v in vars_list]
        self.assertEqual(names, ["PSIppq_phantom", "XadIfd", "Epq"])

    def test_extracts_line_info(self) -> None:
        vars_list = _extract_undersolved_variables(SAMPLE_OMC_OUTPUT)
        self.assertEqual(vars_list[0].line_info, "line 42")
        self.assertEqual(vars_list[1].line_info, "line 46")
        self.assertEqual(vars_list[2].line_info, "line 34")

    def test_extracts_equations(self) -> None:
        vars_list = _extract_undersolved_variables(SAMPLE_OMC_OUTPUT)
        self.assertEqual(len(vars_list[0].equations), 1)
        self.assertEqual(len(vars_list[1].equations), 2)
        self.assertEqual(len(vars_list[2].equations), 4)
        self.assertIn("PSIpp = sqrt(PSIppd ^ 2.0 + PSIppq_phantom ^ 2.0)", vars_list[0].equations)

    def test_returns_empty_for_no_warnings(self) -> None:
        vars_list = _extract_undersolved_variables("Check completed. No errors.")
        self.assertEqual(len(vars_list), 0)


class TestExtractMainError(unittest.TestCase):

    def test_extracts_error_message(self) -> None:
        err = _extract_main_error(SAMPLE_OMC_OUTPUT)
        self.assertIn("Too few equations", err)
        self.assertIn("under-determined system", err)

    def test_returns_empty_for_no_error(self) -> None:
        err = _extract_main_error("Check completed successfully.")
        self.assertEqual(err, "")


class TestFormatOmcErrorExcerpt(unittest.TestCase):

    def test_includes_model_structure(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertIn("Equations: 14", out)
        self.assertIn("Variables: 17", out)
        self.assertIn("Deficit: 3", out)

    def test_includes_error_message(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertIn("Too few equations", out)

    def test_includes_undersolved_variables(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertIn("PSIppq_phantom", out)
        self.assertIn("XadIfd", out)
        self.assertIn("Epq", out)

    def test_strips_file_paths(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertNotIn("/workspace/", out)
        self.assertNotIn("TestModel.mo", out)

    def test_strips_time_fields(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertNotIn("timeFrontend", out)
        self.assertNotIn("timeBackend", out)
        self.assertNotIn("timeSimCode", out)

    def test_strips_simulation_result_record(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertNotIn("record SimulationResult", out)
        self.assertNotIn("resultFile", out)

    def test_preserves_equation_text(self) -> None:
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        self.assertIn("PSIpp = sqrt(PSIppd ^ 2.0 + PSIppq_phantom ^ 2.0)", out)
        self.assertIn("XadIfd = Epq + id * (Xd - Xpd)", out)

    def test_info_completeness(self) -> None:
        """All original variable names and equation texts must be preserved."""
        out = format_omc_error_excerpt(SAMPLE_OMC_OUTPUT)
        vars_list = _extract_undersolved_variables(SAMPLE_OMC_OUTPUT)
        for v in vars_list:
            self.assertIn(v.name, out)
            for eq in v.equations:
                self.assertIn(eq, out)

    def test_noise_reduction(self) -> None:
        """Formatted output should be significantly shorter than raw."""
        raw_len = len(SAMPLE_OMC_OUTPUT)
        out_len = len(format_omc_error_excerpt(SAMPLE_OMC_OUTPUT))
        # Should be at least 40% shorter
        self.assertLess(out_len, raw_len * 0.6, f"Formatted ({out_len}) not much shorter than raw ({raw_len})")

    def test_deficit_mismatch_note(self) -> None:
        """When deficit > listed variables, add a note."""
        # Modify sample to have fewer warnings than deficit
        partial = SAMPLE_OMC_OUTPUT.replace(
            "[/workspace/TestModel.mo:46:3-46:44:writable] Warning: Variable XadIfd",
            ""
        ).replace(
            "[/workspace/TestModel.mo:34:3-34:49:writable] Warning: Variable Epq",
            ""
        )
        out = format_omc_error_excerpt(partial)
        self.assertIn("OMC reports deficit of 3 but only flagged 1", out)

    def test_empty_input(self) -> None:
        out = format_omc_error_excerpt("")
        self.assertEqual(out, "")


class TestCompactFormat(unittest.TestCase):

    def test_compact_output(self) -> None:
        out = format_omc_error_excerpt_compact(SAMPLE_OMC_OUTPUT)
        self.assertIn("Eq=14", out)
        self.assertIn("Var=17", out)
        self.assertIn("Deficit=3", out)
        self.assertIn("PSIppq_phantom", out)
        self.assertIn("XadIfd", out)
        self.assertIn("Epq", out)

    def test_compact_empty(self) -> None:
        out = format_omc_error_excerpt_compact("")
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
