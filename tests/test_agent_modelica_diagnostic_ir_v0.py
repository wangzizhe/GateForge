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
        self.assertEqual(payload.get("observed_phase"), "check")
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
        self.assertEqual(payload.get("observed_phase"), "simulate")
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

    def test_build_diagnostic_detects_gateforge_initialization_marker(self) -> None:
        payload = build_diagnostic_ir_v0(
            output='Simulation failed during initial equation evaluation: assert | gateforge_initialization_infeasible_ab12cd34',
            check_model_pass=True,
            simulate_pass=False,
            expected_stage="simulate",
            declared_failure_type="initialization_infeasible",
        )
        self.assertEqual(payload.get("error_type"), "simulate_error")
        self.assertEqual(payload.get("error_subtype"), "init_failure")
        self.assertEqual(payload.get("stage"), "simulate")
        self.assertEqual(payload.get("observed_phase"), "simulate")
        objects = payload.get("objects") if isinstance(payload.get("objects"), dict) else {}
        self.assertIn("gateforge_initialization_infeasible_ab12cd34", objects.get("assertion_hints") or [])

    def test_build_diagnostic_detects_underconstrained_system_subtype(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Error: System is underdetermined. Too few equations for variables including gateforge_underconstrained_probe_ab12cd34",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="underconstrained_system",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "underconstrained_system")
        self.assertEqual(payload.get("stage"), "check")
        self.assertEqual(payload.get("observed_phase"), "check")
        self.assertIn("restore dropped connects", " | ".join(payload.get("suggested_actions") or []))

    def test_build_diagnostic_detects_structural_count_mismatch_as_underconstrained(self) -> None:
        payload = build_diagnostic_ir_v0(
            output='Check of SmallRDividerV0 completed successfully.\nClass SmallRDividerV0 has 32 equation(s) and 33 variable(s).',
            check_model_pass=False,
            simulate_pass=True,
            expected_stage="check",
            declared_failure_type="underconstrained_system",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "underconstrained_system")
        self.assertEqual(payload.get("stage"), "check")
        self.assertEqual(payload.get("observed_phase"), "check")

    def test_build_diagnostic_detects_underconstrained_signal_even_when_it_surfaces_during_simulate(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Simulation failed: System is structurally singular with too few equations around gateforge_underconstrained_probe_ab12cd34",
            check_model_pass=True,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="underconstrained_system",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "underconstrained_system")
        self.assertEqual(payload.get("stage"), "check")
        self.assertEqual(payload.get("observed_phase"), "simulate")
        self.assertIn("restore dropped connects", " | ".join(payload.get("suggested_actions") or []))

    def test_build_diagnostic_normalizes_declared_underconstrained_compile_unknown_with_structural_context(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Compilation failed near dropped connect path: dangling_connectivity structural_underconstraint gateforge_underconstrained_probe_ab12cd34",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="underconstrained_system",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "underconstrained_system")
        self.assertEqual(payload.get("stage"), "check")
        self.assertEqual(payload.get("observed_phase"), "check")

    def test_build_diagnostic_normalizes_declared_underconstrained_timeout_wrapper(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="TimeoutError: The read operation timed out",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="underconstrained_system",
            declared_context_hints=["drop_connect_equation", "structural_underconstraint"],
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "underconstrained_system")
        self.assertEqual(payload.get("stage"), "check")
        self.assertEqual(payload.get("observed_phase"), "check")

    def test_build_diagnostic_does_not_normalize_plain_timeout_without_structural_context(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="TimeoutError: The read operation timed out",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="underconstrained_system",
        )
        self.assertEqual(payload.get("error_type"), "model_check_error")
        self.assertEqual(payload.get("error_subtype"), "compile_failure_unknown")

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
