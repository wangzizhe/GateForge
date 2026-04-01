"""
Tests for agent_modelica_dual_layer_mutation_v0_3_5.

Covers:
- apply_init_value_collapse: hit/miss/already-zero
- apply_stiff_time_constant_injection: hit/miss/already-stiff
- apply_init_equation_sign_flip: hit/miss/skip-zero
- apply_marked_top_mutation: injection/no-equation-section
- build_dual_layer_task: success, bad operator, bad failure_type
- validate_dual_layer_text_pair: pass/fail cases
- dual_layer=True flag, marker_only_repair=False in output
- execution path annotation present
"""

import unittest

from gateforge.agent_modelica_dual_layer_mutation_v0_3_5 import (
    SAFE_DUAL_LAYER_FAILURE_TYPES,
    TOP_LAYER_STATE_VAR_PREFIX,
    apply_init_equation_sign_flip,
    apply_init_value_collapse,
    apply_marked_top_mutation,
    apply_stiff_time_constant_injection,
    build_dual_layer_task,
    validate_dual_layer_text_pair,
)

# Minimal Modelica model fragments for testing

SIMPLE_MODEL = """\
model SimpleRC
  parameter Real R = 100.0;
  parameter Real C = 0.001;
  Real v(start = 1.0);
equation
  R * C * der(v) = -v;
end SimpleRC;
"""

MODEL_WITH_TAU = """\
model LowPass
  parameter Real tau = 1.0;
  Real y(start = 0.0);
equation
  tau * der(y) = 1.0 - y;
end LowPass;
"""

MODEL_WITH_INIT_EQ = """\
model InitModel
  Real x(start = 0.0);
initial equation
  x = 5.0;
equation
  der(x) = 1.0 - x;
end InitModel;
"""

MODEL_NO_EQUATION = """\
type MyType = Real(unit="kg");
"""

MODEL_NO_PARAM = """\
model NoParam
  Real x;
equation
  der(x) = -x;
end NoParam;
"""


class TestApplyInitValueCollapse(unittest.TestCase):
    def test_collapses_first_real_parameter(self):
        text, audit = apply_init_value_collapse(SIMPLE_MODEL)
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["operator"], "init_value_collapse")
        self.assertIn("0.0", text)
        # Original value replaced
        self.assertIn("R = 0.0", text)
        self.assertEqual(len(audit["mutations"]), 1)
        self.assertFalse(audit["has_gateforge_marker"])

    def test_no_match_returns_original(self):
        text, audit = apply_init_value_collapse(MODEL_NO_PARAM)
        self.assertFalse(audit["applied"])
        self.assertEqual(text, MODEL_NO_PARAM)

    def test_already_zero_skipped(self):
        model = SIMPLE_MODEL.replace("R = 100.0", "R = 0.0")
        text, audit = apply_init_value_collapse(model)
        # Should skip the already-zero one, try C = 0.001
        if audit["applied"]:
            self.assertEqual(audit["mutations"][0]["param_name"], "C")
        # Either way, no crash

    def test_max_targets_respected(self):
        text, audit = apply_init_value_collapse(SIMPLE_MODEL, max_targets=2)
        self.assertTrue(audit["applied"])
        self.assertLessEqual(len(audit["mutations"]), 2)

    def test_custom_collapse_value(self):
        text, audit = apply_init_value_collapse(SIMPLE_MODEL, collapse_value="-1.0")
        self.assertTrue(audit["applied"])
        self.assertIn("-1.0", text)


class TestApplyStiffTimeConstantInjection(unittest.TestCase):
    def test_collapses_tau(self):
        text, audit = apply_stiff_time_constant_injection(MODEL_WITH_TAU)
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["operator"], "stiff_time_constant_injection")
        self.assertIn("1e-9", text)
        self.assertFalse(audit["has_gateforge_marker"])
        self.assertEqual(audit["mutations"][0]["param_name"], "tau")

    def test_no_time_constant_param(self):
        text, audit = apply_stiff_time_constant_injection(SIMPLE_MODEL)
        # SIMPLE_MODEL has R and C, not tau/T names
        self.assertFalse(audit["applied"])

    def test_already_stiff_skipped(self):
        model = MODEL_WITH_TAU.replace("tau = 1.0", "tau = 1e-12")
        text, audit = apply_stiff_time_constant_injection(model)
        self.assertFalse(audit["applied"])

    def test_custom_stiff_value(self):
        text, audit = apply_stiff_time_constant_injection(MODEL_WITH_TAU, stiff_value="1e-6")
        self.assertTrue(audit["applied"])
        self.assertIn("1e-6", text)


class TestApplyInitEquationSignFlip(unittest.TestCase):
    def test_flips_initial_equation(self):
        text, audit = apply_init_equation_sign_flip(MODEL_WITH_INIT_EQ)
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["operator"], "init_equation_sign_flip")
        self.assertIn("-(5.0)", text)
        self.assertFalse(audit["has_gateforge_marker"])
        self.assertEqual(audit["mutations"][0]["lhs"], "x")

    def test_no_initial_equation_section(self):
        text, audit = apply_init_equation_sign_flip(SIMPLE_MODEL)
        self.assertFalse(audit["applied"])

    def test_zero_rhs_skipped(self):
        model = MODEL_WITH_INIT_EQ.replace("x = 5.0", "x = 0")
        text, audit = apply_init_equation_sign_flip(model)
        # zero rhs should be skipped
        self.assertFalse(audit["applied"])

    def test_already_negated_skipped(self):
        model = MODEL_WITH_INIT_EQ.replace("x = 5.0", "x = -5.0")
        text, audit = apply_init_equation_sign_flip(model)
        # starts with "-", should be skipped
        self.assertFalse(audit["applied"])


class TestApplyMarkedTopMutation(unittest.TestCase):
    def test_injects_gf_state_var(self):
        text, audit = apply_marked_top_mutation(SIMPLE_MODEL)
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["operator"], "simulate_error_top_injection")
        self.assertTrue(audit["has_gateforge_marker"])
        self.assertIn(TOP_LAYER_STATE_VAR_PREFIX, text)
        self.assertIn("GateForge mutation", text)

    def test_no_equation_section_fails(self):
        text, audit = apply_marked_top_mutation(MODEL_NO_EQUATION)
        self.assertFalse(audit["applied"])
        self.assertEqual(text, MODEL_NO_EQUATION)

    def test_custom_var_suffix(self):
        text, audit = apply_marked_top_mutation(SIMPLE_MODEL, var_suffix="abc123")
        self.assertIn(f"{TOP_LAYER_STATE_VAR_PREFIX}abc123", text)

    def test_injected_before_equation_keyword(self):
        text, audit = apply_marked_top_mutation(SIMPLE_MODEL)
        # The gf var should appear before the equation block
        gf_pos = text.index(TOP_LAYER_STATE_VAR_PREFIX)
        eq_pos = text.index("\nequation\n")
        self.assertLess(gf_pos, eq_pos)

    def test_source_text_unchanged(self):
        # Original should not have the marker
        self.assertNotIn(TOP_LAYER_STATE_VAR_PREFIX, SIMPLE_MODEL)


class TestBuildDualLayerTask(unittest.TestCase):
    def _build(self, operator="init_value_collapse", model=SIMPLE_MODEL):
        return build_dual_layer_task(
            task_id="test_task_001",
            clean_source_text=model,
            source_model_path="/fake/path/model.mo",
            source_library="test_lib",
            model_hint="SimpleRC",
            hidden_base_operator=operator,
        )

    def test_returns_dual_layer_flag(self):
        task = self._build()
        self.assertTrue(task["dual_layer_mutation"])
        self.assertFalse(task["marker_only_repair"])

    def test_declared_failure_type_is_safe(self):
        task = self._build()
        self.assertIn(task["declared_failure_type"], SAFE_DUAL_LAYER_FAILURE_TYPES)

    def test_source_text_has_no_marker(self):
        task = self._build()
        self.assertNotIn(TOP_LAYER_STATE_VAR_PREFIX, task["source_model_text"])

    def test_mutated_text_has_marker(self):
        task = self._build()
        self.assertIn(TOP_LAYER_STATE_VAR_PREFIX, task["mutated_model_text"])

    def test_texts_are_different(self):
        task = self._build()
        self.assertNotEqual(task["source_model_text"], task["mutated_model_text"])

    def test_mutation_spec_has_both_layers(self):
        task = self._build()
        spec = task["mutation_spec"]
        self.assertIn("hidden_base", spec)
        self.assertIn("marked_top", spec)
        self.assertFalse(spec["hidden_base"]["has_gateforge_marker"])
        self.assertTrue(spec["marked_top"]["has_gateforge_marker"])

    def test_execution_path_annotation(self):
        task = self._build()
        path = task["expected_execution_path"]
        self.assertIn("round_1", path)
        self.assertIn("round_2", path)

    def test_bad_operator_raises(self):
        with self.assertRaises(ValueError):
            build_dual_layer_task(
                task_id="t",
                clean_source_text=SIMPLE_MODEL,
                source_model_path="/fake/path.mo",
                source_library="lib",
                model_hint="m",
                hidden_base_operator="nonexistent_operator",
            )

    def test_bad_failure_type_raises(self):
        with self.assertRaises(ValueError):
            build_dual_layer_task(
                task_id="t",
                clean_source_text=SIMPLE_MODEL,
                source_model_path="/fake/path.mo",
                source_library="lib",
                model_hint="m",
                hidden_base_operator="init_value_collapse",
                declared_failure_type="coupled_conflict_failure",  # NOT safe
            )

    def test_stiff_time_constant_operator(self):
        task = self._build(operator="stiff_time_constant_injection", model=MODEL_WITH_TAU)
        self.assertTrue(task["dual_layer_mutation"])
        self.assertIn("1e-9", task["source_model_text"])

    def test_init_sign_flip_operator(self):
        task = self._build(operator="init_equation_sign_flip", model=MODEL_WITH_INIT_EQ)
        self.assertTrue(task["dual_layer_mutation"])
        self.assertIn("-(5.0)", task["source_model_text"])

    def test_unapplicable_operator_raises(self):
        # MODEL_NO_PARAM has no Real parameters to collapse
        with self.assertRaises(RuntimeError):
            build_dual_layer_task(
                task_id="t",
                clean_source_text=MODEL_NO_PARAM,
                source_model_path="/fake/path.mo",
                source_library="lib",
                model_hint="m",
                hidden_base_operator="init_value_collapse",
            )


class TestValidateDualLayerTextPair(unittest.TestCase):
    def _make_pair(self):
        src, _ = apply_init_value_collapse(SIMPLE_MODEL)
        mut, _ = apply_marked_top_mutation(src)
        return src, mut

    def test_valid_pair_passes(self):
        src, mut = self._make_pair()
        result = validate_dual_layer_text_pair(src, mut)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["reasons"], [])

    def test_identical_texts_fail(self):
        result = validate_dual_layer_text_pair(SIMPLE_MODEL, SIMPLE_MODEL)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("source_and_mutated_are_identical", result["reasons"])

    def test_marker_in_source_fails(self):
        src_with_marker = SIMPLE_MODEL + f"\n  Real {TOP_LAYER_STATE_VAR_PREFIX}x;\n"
        _, mut = self._make_pair()
        result = validate_dual_layer_text_pair(src_with_marker, mut)
        self.assertEqual(result["status"], "FAIL")

    def test_missing_marker_in_mutated_fails(self):
        src, _ = self._make_pair()
        # mutated without marker = same as source
        result = validate_dual_layer_text_pair(src, src)
        self.assertIn("source_and_mutated_are_identical", result["reasons"])

    def test_schema_version_present(self):
        src, mut = self._make_pair()
        result = validate_dual_layer_text_pair(src, mut)
        self.assertIn("schema_version", result)


if __name__ == "__main__":
    unittest.main()
