import unittest

from gateforge.agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0


class AgentModelicaDiagnosticIRV0Tests(unittest.TestCase):
    def test_build_diagnostic_maps_parse_error_to_canonical_type_and_legacy_alias(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Error: No viable alternative near token: __gf_state_301500",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="model_check_error",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "parse_lexer_error")
        self.assertEqual(payload.get("error_type_legacy"), "script_parse_error")
        self.assertEqual(payload.get("stage"), "check")
        objects = payload.get("objects") if isinstance(payload.get("objects"), dict) else {}
        self.assertIn("__gf_state_301500", objects.get("injected_states") or [])
        compat = payload.get("compat") if isinstance(payload.get("compat"), dict) else {}
        self.assertTrue(bool(compat.get("legacy_script_parse_error")))

    def test_build_diagnostic_detects_numerical_instability(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Simulation failed: integrator failed due to step size",
            check_model_pass=True,
            simulate_pass=False,
            expected_stage="simulate",
            declared_failure_type="simulate_error",
        )
        self.assertEqual(payload.get("error_type"), "numerical_instability")
        self.assertEqual(payload.get("error_subtype"), "solver_divergence")
        self.assertEqual(payload.get("stage"), "simulate")
        self.assertIn("stabilize solver-facing dynamics", " | ".join(payload.get("suggested_actions") or []))

    def test_build_diagnostic_detects_undefined_symbol_subtype(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Error: Variable __gf_undef_301300 not found in scope A1",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="model_check_error",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "undefined_symbol")
        objects = payload.get("objects") if isinstance(payload.get("objects"), dict) else {}
        self.assertIn("__gf_undef_301300", objects.get("undefined_symbols") or [])

    def test_build_diagnostic_detects_connector_mismatch_subtype(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Error: Type mismatch in connect(src.p, load.n): incompatible connector",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="model_check_error",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "connector_mismatch")
        objects = payload.get("objects") if isinstance(payload.get("objects"), dict) else {}
        self.assertTrue(bool(objects.get("connector_hints")))

    def test_build_diagnostic_detects_assertion_violation_subtype(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Simulation terminated by assertion: gateforge_voltage_limit",
            check_model_pass=True,
            simulate_pass=False,
            expected_stage="simulate",
            declared_failure_type="constraint_violation",
        )
        self.assertEqual(payload.get("error_type"), "constraint_violation")
        self.assertEqual(payload.get("error_subtype"), "assertion_violation")
        objects = payload.get("objects") if isinstance(payload.get("objects"), dict) else {}
        self.assertIn("gateforge_voltage_limit", objects.get("assertion_hints") or [])

    def test_build_diagnostic_detects_timeout_subtype(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Simulation timeout expired after 90s",
            check_model_pass=True,
            simulate_pass=False,
            expected_stage="simulate",
            declared_failure_type="simulate_error",
        )
        self.assertEqual(payload.get("error_type"), "numerical_instability")
        self.assertEqual(payload.get("error_subtype"), "timeout")

    def test_build_diagnostic_normalizes_legacy_declared_failure_type(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Error: No viable alternative near token: __gf_state_301500",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="script_parse_error",
        )
        self.assertEqual(payload.get("declared_failure_type"), "script_parse_error")
        self.assertEqual(payload.get("declared_failure_type_canonical"), "model_check_error")


if __name__ == "__main__":
    unittest.main()
