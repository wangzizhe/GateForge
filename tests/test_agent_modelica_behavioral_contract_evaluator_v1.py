"""Tests for Behavioral Contract Evaluator.

All tests are pure-function tests: no Docker, LLM, OMC, or filesystem
dependencies.  Organised by function, roughly following the module order.
"""
from __future__ import annotations

import unittest

from gateforge.agent_modelica_behavioral_contract_evaluator_v1 import (
    BEHAVIORAL_MARKER_PREFIX,
    BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX,
    apply_initialization_marker_repair,
    evaluate_behavioral_contract_from_model_text,
    normalize_behavioral_contract_text,
)


# ===================================================================
# normalize_behavioral_contract_text
# ===================================================================


class TestNormalizeBehavioralContractText(unittest.TestCase):
    def test_strips_behavioral_marker_comments(self) -> None:
        text = (
            "model Foo\n"
            f"  // {BEHAVIORAL_MARKER_PREFIX}_violation\n"
            "  parameter Real x = 1.0;\n"
            "end Foo;"
        )
        result = normalize_behavioral_contract_text(text)
        self.assertNotIn(BEHAVIORAL_MARKER_PREFIX, result)
        self.assertIn("parameter Real x", result)

    def test_strips_robustness_marker_comments(self) -> None:
        text = (
            "model Bar\n"
            f"  // {BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX}_violation\n"
            "  parameter Real y = 2.0;\n"
            "end Bar;"
        )
        result = normalize_behavioral_contract_text(text)
        self.assertNotIn(BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX, result)
        self.assertIn("parameter Real y", result)

    def test_normalises_whitespace(self) -> None:
        text = "model   Foo\n  parameter   Real  x  =  1.0;\nend   Foo;"
        result = normalize_behavioral_contract_text(text)
        self.assertIn("parameter Real x = 1.0;", result)

    def test_empty_string(self) -> None:
        self.assertEqual(normalize_behavioral_contract_text(""), "")

    def test_none_coercion(self) -> None:
        # None should not raise
        result = normalize_behavioral_contract_text(None)  # type: ignore[arg-type]
        self.assertEqual(result, "")

    def test_identical_texts_normalize_equal(self) -> None:
        text = "model X\n  parameter Real p = 1.0;\nend X;"
        a = normalize_behavioral_contract_text(text)
        b = normalize_behavioral_contract_text(text)
        self.assertEqual(a, b)

    def test_texts_differing_only_in_markers_normalize_equal(self) -> None:
        base = "model X\n  parameter Real p = 1.0;\nend X;"
        with_marker = (
            "model X\n"
            f"  // {BEHAVIORAL_MARKER_PREFIX}_some_id\n"
            "  parameter Real p = 1.0;\n"
            "end X;"
        )
        self.assertEqual(
            normalize_behavioral_contract_text(base),
            normalize_behavioral_contract_text(with_marker),
        )


# ===================================================================
# evaluate_behavioral_contract_from_model_text
# ===================================================================


_SIMPLE_SOURCE = "model SimpleA\n  parameter Real k = 1.0;\nend SimpleA;"


class TestEvaluateBehavioralContractUnsupportedType(unittest.TestCase):
    def test_unknown_failure_type_returns_none(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=_SIMPLE_SOURCE,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="unknown_type",
        )
        self.assertIsNone(result)

    def test_empty_failure_type_returns_none(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=_SIMPLE_SOURCE,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="",
        )
        self.assertIsNone(result)


class TestEvaluateSteadyStateTargetViolation(unittest.TestCase):
    def test_pass_when_texts_match(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=_SIMPLE_SOURCE,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="steady_state_target_violation",
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["pass"])
        self.assertEqual(result["contract_fail_bucket"], "")

    def test_fail_when_texts_differ(self) -> None:
        current = "model SimpleA\n  parameter Real k = 2.0;\nend SimpleA;"
        result = evaluate_behavioral_contract_from_model_text(
            current_text=current,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="steady_state_target_violation",
        )
        self.assertIsNotNone(result)
        self.assertFalse(result["pass"])
        self.assertNotEqual(result["contract_fail_bucket"], "")

    def test_result_structure(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=_SIMPLE_SOURCE,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="steady_state_target_violation",
        )
        self.assertIn("pass", result)
        self.assertIn("reasons", result)
        self.assertIn("contract_fail_bucket", result)
        self.assertIn("scenario_results", result)


class TestEvaluateTransientResponseContractViolation(unittest.TestCase):
    def test_pass_when_texts_match(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=_SIMPLE_SOURCE,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="transient_response_contract_violation",
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["pass"])

    def test_fail_when_texts_differ(self) -> None:
        current = "model SimpleA\n  parameter Real k = 3.0;\nend SimpleA;"
        result = evaluate_behavioral_contract_from_model_text(
            current_text=current,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="transient_response_contract_violation",
        )
        self.assertFalse(result["pass"])


class TestEvaluateModeTransitionContractViolation(unittest.TestCase):
    def test_pass_when_texts_match(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=_SIMPLE_SOURCE,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="mode_transition_contract_violation",
        )
        self.assertTrue(result["pass"])


class TestEvaluateRobustnessTypes(unittest.TestCase):
    _ROBUSTNESS_TYPES = [
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    ]

    def test_pass_produces_three_passing_scenarios(self) -> None:
        for ft in self._ROBUSTNESS_TYPES:
            with self.subTest(failure_type=ft):
                result = evaluate_behavioral_contract_from_model_text(
                    current_text=_SIMPLE_SOURCE,
                    source_model_text=_SIMPLE_SOURCE,
                    failure_type=ft,
                )
                self.assertTrue(result["pass"])
                self.assertEqual(len(result["scenario_results"]), 3)
                self.assertTrue(all(s["pass"] for s in result["scenario_results"]))

    def test_fail_produces_mixed_scenarios(self) -> None:
        current = "model SimpleA\n  parameter Real k = 5.0;\nend SimpleA;"
        for ft in self._ROBUSTNESS_TYPES:
            with self.subTest(failure_type=ft):
                result = evaluate_behavioral_contract_from_model_text(
                    current_text=current,
                    source_model_text=_SIMPLE_SOURCE,
                    failure_type=ft,
                )
                self.assertFalse(result["pass"])
                scenario_pass_flags = [s["pass"] for s in result["scenario_results"]]
                self.assertIn(False, scenario_pass_flags)


class TestEvaluateStabilityThenBehaviorPlantB(unittest.TestCase):
    # PlantB with original stability-violating params => stage_1
    _PLANTB_STAGE1 = "model PlantB\n  parameter Real height = 1.2;\n  parameter Real duration = 1.1;\nend PlantB;"
    # PlantB with startTime indicating stage_2 behavior_timing_branch
    _PLANTB_TIMING = "model PlantB\n  parameter Real startTime = 0.8;\n  parameter Real height = 0.5;\nend PlantB;"
    # PlantB with no violation markers => passed
    _PLANTB_PASS = "model PlantB\n  parameter Real x = 1.0;\nend PlantB;"

    def test_stage_1_still_violated(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._PLANTB_STAGE1,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="stability_then_behavior",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "stage_1")
        self.assertFalse(result.get("multi_step_transition_seen"))

    def test_timing_branch_exposed(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._PLANTB_TIMING,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="stability_then_behavior",
        )
        self.assertIsNotNone(result)
        self.assertIn(result.get("multi_step_stage"), {"stage_2", "passed"})

    def test_passed_when_cleared(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._PLANTB_PASS,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="stability_then_behavior",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "passed")
        self.assertTrue(result.get("multi_step_transition_seen"))


class TestEvaluateStabilityThenBehaviorSwitchA(unittest.TestCase):
    # SwitchA with stability-violating k => stage_1
    _SWITCHA_STAGE1 = "model SwitchA\n  parameter Real k = 1.18;\nend SwitchA;"
    # SwitchA cleared
    _SWITCHA_PASS = "model SwitchA\n  parameter Real k = 1.0;\nend SwitchA;"

    def test_stage_1_stability_violated(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._SWITCHA_STAGE1,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="stability_then_behavior",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "stage_1")

    def test_passed_when_cleared(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._SWITCHA_PASS,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="stability_then_behavior",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "passed")


class TestEvaluateBehaviorThenRobustness(unittest.TestCase):
    _SWITCHB_STAGE1 = "model SwitchB\n  parameter Real startTime = 0.75;\n  parameter Real freqHz = 1.6;\nend SwitchB;"
    _SWITCHB_PASS = "model SwitchB\n  parameter Real startTime = 1.0;\n  parameter Real freqHz = 1.0;\nend SwitchB;"

    def test_stage_1_nominal_still_failing(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._SWITCHB_STAGE1,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="behavior_then_robustness",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "stage_1")

    def test_passed_when_cleared(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._SWITCHB_PASS,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="behavior_then_robustness",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "passed")


class TestEvaluateSwitchThenRecovery(unittest.TestCase):
    _PLANTB_SWITCH_STAGE1 = (
        "model PlantB\n"
        "  parameter Real startTime = 0.6;\n"
        "  parameter Real duration = 1.1;\n"
        "end PlantB;"
    )
    _PLANTB_SWITCH_PASS = (
        "model PlantB\n"
        "  parameter Real startTime = 1.0;\n"
        "  parameter Real duration = 0.5;\n"
        "end PlantB;"
    )

    def test_stage_1_switch_unstable(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._PLANTB_SWITCH_STAGE1,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="switch_then_recovery",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "stage_1")

    def test_passed_when_cleared(self) -> None:
        result = evaluate_behavioral_contract_from_model_text(
            current_text=self._PLANTB_SWITCH_PASS,
            source_model_text=_SIMPLE_SOURCE,
            failure_type="switch_then_recovery",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get("multi_step_stage"), "passed")


class TestEvaluateReturnTypeConsistency(unittest.TestCase):
    _SUPPORTED_TYPES = [
        "steady_state_target_violation",
        "transient_response_contract_violation",
        "mode_transition_contract_violation",
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    ]

    def test_all_supported_types_return_dict(self) -> None:
        for ft in self._SUPPORTED_TYPES:
            with self.subTest(failure_type=ft):
                result = evaluate_behavioral_contract_from_model_text(
                    current_text=_SIMPLE_SOURCE,
                    source_model_text=_SIMPLE_SOURCE,
                    failure_type=ft,
                )
                self.assertIsInstance(result, dict)

    def test_markers_only_difference_passes(self) -> None:
        source = "model M\n  parameter Real x = 1.0;\nend M;"
        current_with_marker = (
            "model M\n"
            f"  // {BEHAVIORAL_MARKER_PREFIX}_violation\n"
            "  parameter Real x = 1.0;\n"
            "end M;"
        )
        for ft in self._SUPPORTED_TYPES:
            with self.subTest(failure_type=ft):
                result = evaluate_behavioral_contract_from_model_text(
                    current_text=current_with_marker,
                    source_model_text=source,
                    failure_type=ft,
                )
                # texts normalize to same => pass
                self.assertTrue(result["pass"])


# ===================================================================
# apply_initialization_marker_repair
# ===================================================================


class TestApplyInitializationMarkerRepair(unittest.TestCase):
    def test_unsupported_failure_type(self) -> None:
        text = "model Foo\nend Foo;"
        result_text, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="structural_error",
        )
        self.assertEqual(result_text, text)
        self.assertFalse(audit["applied"])

    def test_empty_model_text(self) -> None:
        result_text, audit = apply_initialization_marker_repair(
            current_text="",
            declared_failure_type="initialization_infeasible",
        )
        self.assertEqual(result_text, "")
        self.assertFalse(audit["applied"])

    def test_no_marker_in_text(self) -> None:
        text = "model Foo\n  parameter Real x = 1.0;\nend Foo;"
        result_text, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertEqual(result_text, text)
        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "initialization_marker_not_detected")

    def test_removes_marker_line(self) -> None:
        text = (
            "model Foo\n"
            "  parameter Real x = 1.0;\n"
            "  // gateforge_initialization_infeasible_violation\n"
            "end Foo;"
        )
        result_text, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertTrue(audit["applied"])
        self.assertNotIn("gateforge_initialization_infeasible", result_text)
        self.assertIn("parameter Real x", result_text)

    def test_removes_initial_equation_block(self) -> None:
        text = (
            "model Foo\n"
            "  parameter Real x = 1.0;\n"
            "initial equation\n"
            "  // gateforge_initialization_infeasible_violation\n"
            "end Foo;"
        )
        result_text, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertTrue(audit["applied"])
        self.assertNotIn("gateforge_initialization_infeasible", result_text)
        self.assertNotIn("initial equation", result_text)

    def test_audit_counts_removed_lines(self) -> None:
        text = (
            "model Foo\n"
            "  // gateforge_initialization_infeasible_violation\n"
            "end Foo;"
        )
        _, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertTrue(audit["applied"])
        self.assertGreater(audit["removed_line_count"], 0)

    def test_removes_preceding_blank_lines(self) -> None:
        text = (
            "model Foo\n"
            "  parameter Real x = 1.0;\n"
            "\n"
            "  // gateforge_initialization_infeasible_violation\n"
            "end Foo;"
        )
        result_text, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertTrue(audit["applied"])
        self.assertNotIn("gateforge_initialization_infeasible", result_text)

    def test_case_insensitive_marker_detection(self) -> None:
        text = (
            "model Foo\n"
            "  // GATEFORGE_INITIALIZATION_INFEASIBLE_violation\n"
            "end Foo;"
        )
        _, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertTrue(audit["applied"])

    def test_returns_original_text_when_no_change(self) -> None:
        text = "model Foo\n  parameter Real x = 1.0;\nend Foo;"
        result_text, audit = apply_initialization_marker_repair(
            current_text=text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertEqual(result_text, text)
        self.assertFalse(audit["applied"])


# ===================================================================
# Module-level constants
# ===================================================================


class TestModuleConstants(unittest.TestCase):
    def test_behavioral_marker_prefix_value(self) -> None:
        self.assertEqual(BEHAVIORAL_MARKER_PREFIX, "gateforge_behavioral_contract_violation")

    def test_behavioral_robustness_marker_prefix_value(self) -> None:
        self.assertEqual(
            BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX,
            "gateforge_behavioral_robustness_violation",
        )


if __name__ == "__main__":
    unittest.main()
