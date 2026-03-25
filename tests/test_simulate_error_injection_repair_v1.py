"""
Tests for _apply_simulate_error_injection_repair in the live executor.

Covers:
- Pattern 1: __gf_state_* + der = 1.0/0.0 (simulation instability)
- Pattern 2: __gf_tau_* + __gf_state_* + der = ... / __gf_tau_* (zero time constant)
- No-op cases: wrong failure type, no GF injection detected
- Large model: only injected lines are removed, rest is preserved
"""

import unittest

from gateforge.agent_modelica_live_executor_gemini_v1 import (
    _apply_simulate_error_injection_repair,
)

_P1 = """\
model A1
  Real x;
  Real __gf_state_301100(start=1.0);
  // GateForge mutation: simulation instability
equation
  der(__gf_state_301100) = 1.0 / 0.0;
  der(x) = -x;
end A1;"""

_P1_EXPECTED = """\
model A1
  Real x;
equation
  der(x) = -x;
end A1;"""

_P2 = """\
model A1
  Real x;
  // GateForge mutation: zero time constant
  parameter Real __gf_tau_301200 = 0.0;
  Real __gf_state_301200(start=0.0);
equation
  der(__gf_state_301200) = (1.0 - __gf_state_301200) / __gf_tau_301200;
  der(x) = -x;
end A1;"""

_P2_EXPECTED = """\
model A1
  Real x;
equation
  der(x) = -x;
end A1;"""

_CLEAN = """\
model A1
  Real x;
equation
  der(x) = -x;
end A1;"""


class TestApplySimulateErrorInjectionRepair(unittest.TestCase):

    # --- Pattern 1: division by zero ---

    def test_p1_applied(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="simulate_error"
        )
        self.assertTrue(audit["applied"])

    def test_p1_removed_count(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="simulate_error"
        )
        self.assertEqual(audit["removed_line_count"], 3)

    def test_p1_repaired_text(self):
        result, _ = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="simulate_error"
        )
        self.assertEqual(result.strip(), _P1_EXPECTED.strip())

    def test_p1_var_names_reported(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="simulate_error"
        )
        self.assertIn("__gf_state_301100", audit["gf_var_names"])

    # --- Pattern 2: zero time constant ---

    def test_p2_applied(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P2, declared_failure_type="simulate_error"
        )
        self.assertTrue(audit["applied"])

    def test_p2_removed_count(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P2, declared_failure_type="simulate_error"
        )
        self.assertEqual(audit["removed_line_count"], 4)

    def test_p2_repaired_text(self):
        result, _ = _apply_simulate_error_injection_repair(
            current_text=_P2, declared_failure_type="simulate_error"
        )
        self.assertEqual(result.strip(), _P2_EXPECTED.strip())

    def test_p2_both_var_names_reported(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P2, declared_failure_type="simulate_error"
        )
        names = audit["gf_var_names"]
        self.assertIn("__gf_state_301200", names)
        self.assertIn("__gf_tau_301200", names)

    # --- No-op cases ---

    def test_wrong_failure_type_model_check_error(self):
        result, audit = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="model_check_error"
        )
        self.assertFalse(audit["applied"])
        self.assertEqual(result, _P1)

    def test_wrong_failure_type_semantic_regression(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="semantic_regression"
        )
        self.assertFalse(audit["applied"])

    def test_empty_failure_type(self):
        _, audit = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type=""
        )
        self.assertFalse(audit["applied"])

    def test_no_injection_clean_model(self):
        result, audit = _apply_simulate_error_injection_repair(
            current_text=_CLEAN, declared_failure_type="simulate_error"
        )
        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "no_gf_injection_detected")
        self.assertEqual(result, _CLEAN)

    def test_empty_text(self):
        result, audit = _apply_simulate_error_injection_repair(
            current_text="", declared_failure_type="simulate_error"
        )
        self.assertFalse(audit["applied"])

    # --- Idempotency ---

    def test_idempotent_p1(self):
        r1, _ = _apply_simulate_error_injection_repair(
            current_text=_P1, declared_failure_type="simulate_error"
        )
        r2, audit2 = _apply_simulate_error_injection_repair(
            current_text=r1, declared_failure_type="simulate_error"
        )
        self.assertFalse(audit2["applied"])
        self.assertEqual(r1, r2)

    def test_idempotent_p2(self):
        r1, _ = _apply_simulate_error_injection_repair(
            current_text=_P2, declared_failure_type="simulate_error"
        )
        r2, audit2 = _apply_simulate_error_injection_repair(
            current_text=r1, declared_failure_type="simulate_error"
        )
        self.assertFalse(audit2["applied"])
        self.assertEqual(r1, r2)

    # --- Large model: non-injected lines preserved ---

    def test_large_model_preserves_non_injected_lines(self):
        large = """\
model LargeGrid
  Real x;
  Real y;
  Real z;
  parameter Real p1 = 1;
  Real __gf_state_102100(start=1.0);
  // GateForge mutation: simulation instability
equation
  der(x) = -x;
  der(y) = -y;
  der(z) = -z;
  der(__gf_state_102100) = 1.0 / 0.0;
end LargeGrid;"""
        result, audit = _apply_simulate_error_injection_repair(
            current_text=large, declared_failure_type="simulate_error"
        )
        self.assertTrue(audit["applied"])
        self.assertNotIn("__gf_state_102100", result)
        self.assertIn("der(x) = -x;", result)
        self.assertIn("der(y) = -y;", result)
        self.assertIn("der(z) = -z;", result)
        self.assertIn("parameter Real p1 = 1;", result)


if __name__ == "__main__":
    unittest.main()
