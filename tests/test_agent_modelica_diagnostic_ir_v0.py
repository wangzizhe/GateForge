import unittest

from gateforge.agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0


class AgentModelicaDiagnosticIRV0Tests(unittest.TestCase):
    def test_build_diagnostic_detects_script_parse_error(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Error: No viable alternative near token: __gf_state_301500",
            check_model_pass=False,
            simulate_pass=False,
            expected_stage="check",
            declared_failure_type="model_check_error",
        )
        self.assertEqual(payload.get("error_type"), "script_parse_error")
        self.assertEqual(payload.get("stage"), "check")
        objects = payload.get("objects") if isinstance(payload.get("objects"), dict) else {}
        self.assertIn("__gf_state_301500", objects.get("injected_states") or [])

    def test_build_diagnostic_detects_simulate_error(self) -> None:
        payload = build_diagnostic_ir_v0(
            output="Simulation failed: integrator failed due to step size",
            check_model_pass=True,
            simulate_pass=False,
            expected_stage="simulate",
            declared_failure_type="simulate_error",
        )
        self.assertEqual(payload.get("error_type"), "simulate_error")
        self.assertEqual(payload.get("stage"), "simulate")
        self.assertIn("stabilize initialization", " | ".join(payload.get("suggested_actions") or []))


if __name__ == "__main__":
    unittest.main()
