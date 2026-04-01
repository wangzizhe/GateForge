from __future__ import annotations

import unittest

from gateforge.agent_modelica_dual_layer_mutation_v0_3_6 import (
    FAMILY_ID,
    HIDDEN_BASE_OPERATORS,
    apply_paired_value_bias_shift,
    apply_paired_value_collapse,
    build_dual_layer_multi_param_task,
)
from gateforge.agent_modelica_dual_layer_mutation_v0_3_5 import TOP_LAYER_TAU_PREFIX


SIMPLE_MODEL = """\
model TwoParamRC
  parameter Real R = 100.0;
  parameter Real C = 0.001;
  Real v(start = 1.0);
equation
  R * C * der(v) = -v;
end TwoParamRC;
"""


class AgentModelicaDualLayerMutationV036Tests(unittest.TestCase):
    def test_paired_value_collapse_mutates_two_parameters(self) -> None:
        text, audit = apply_paired_value_collapse(SIMPLE_MODEL)
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["operator"], "paired_value_collapse")
        self.assertEqual(audit["mutation_count"], 2)
        self.assertIn("R = 0.0", text)
        self.assertIn("C = 0.0", text)

    def test_paired_value_bias_shift_mutates_two_parameters(self) -> None:
        text, audit = apply_paired_value_bias_shift(SIMPLE_MODEL)
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["operator"], "paired_value_bias_shift")
        self.assertEqual(audit["mutation_count"], 2)
        self.assertIn("0.1", text)
        self.assertIn("10.0", text)

    def test_build_task_adds_v036_family_and_multi_parameter_expectation(self) -> None:
        task = build_dual_layer_multi_param_task(
            task_id="v036_task",
            clean_source_text=SIMPLE_MODEL,
            source_model_path="/tmp/twoparam.mo",
            source_library="testlib",
            model_hint="TwoParamRC",
        )
        self.assertEqual(task["v0_3_6_family_id"], FAMILY_ID)
        self.assertTrue(task["dual_layer_mutation"])
        self.assertTrue(task["multi_parameter_hidden_base"])
        self.assertEqual(task["baseline_expectation"]["single_sweep_expected_to_fail"], True)
        self.assertEqual(task["hidden_base_operator"], "paired_value_collapse")

    def test_source_has_no_marker_but_mutated_has_marker(self) -> None:
        task = build_dual_layer_multi_param_task(
            task_id="v036_task",
            clean_source_text=SIMPLE_MODEL,
            source_model_path="/tmp/twoparam.mo",
            source_library="testlib",
            model_hint="TwoParamRC",
        )
        self.assertNotIn(TOP_LAYER_TAU_PREFIX, task["source_model_text"])
        self.assertIn(TOP_LAYER_TAU_PREFIX, task["mutated_model_text"])

    def test_bad_operator_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_dual_layer_multi_param_task(
                task_id="v036_task",
                clean_source_text=SIMPLE_MODEL,
                source_model_path="/tmp/twoparam.mo",
                source_library="testlib",
                model_hint="TwoParamRC",
                hidden_base_operator="not_real",
            )

    def test_public_operator_set_nonempty(self) -> None:
        self.assertIn("paired_value_collapse", HIDDEN_BASE_OPERATORS)
        self.assertIn("paired_value_bias_shift", HIDDEN_BASE_OPERATORS)


if __name__ == "__main__":
    unittest.main()
