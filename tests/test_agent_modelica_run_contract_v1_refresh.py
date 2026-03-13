import unittest

from gateforge.agent_modelica_run_contract_v1 import (
    _pick_manifestation_live_attempt,
    _prefer_diagnostic_failure_type,
    _should_refresh_diagnostic_ir,
)


class AgentModelicaRunContractV1RefreshTests(unittest.TestCase):
    def test_refreshes_underconstrained_compile_unknown_diagnostic(self) -> None:
        task = {"failure_type": "underconstrained_system"}
        diagnostic_ir = {"error_type": "model_check_error", "error_subtype": "compile_failure_unknown"}
        self.assertTrue(_should_refresh_diagnostic_ir(task, diagnostic_ir))

    def test_keeps_underconstrained_structural_diagnostic(self) -> None:
        task = {"failure_type": "underconstrained_system"}
        diagnostic_ir = {"error_type": "model_check_error", "error_subtype": "underconstrained_system"}
        self.assertFalse(_should_refresh_diagnostic_ir(task, diagnostic_ir))

    def test_does_not_refresh_other_failure_types(self) -> None:
        task = {"failure_type": "connector_mismatch"}
        diagnostic_ir = {"error_type": "model_check_error", "error_subtype": "compile_failure_unknown"}
        self.assertFalse(_should_refresh_diagnostic_ir(task, diagnostic_ir))

    def test_prefers_diagnostic_type_over_executor_runtime_wrapper(self) -> None:
        preferred = _prefer_diagnostic_failure_type(
            observed_failure_type="executor_runtime_error",
            diagnostic_ir={"error_type": "model_check_error", "error_subtype": "underconstrained_system"},
        )
        self.assertEqual(preferred, "model_check_error")

    def test_keeps_specific_non_wrapper_observed_type(self) -> None:
        preferred = _prefer_diagnostic_failure_type(
            observed_failure_type="simulate_error",
            diagnostic_ir={"error_type": "model_check_error", "error_subtype": "underconstrained_system"},
        )
        self.assertEqual(preferred, "simulate_error")

    def test_pick_manifestation_prefers_diagnostic_type_over_wrapper(self) -> None:
        attempts = [
            {
                "observed_failure_type": "executor_runtime_error",
                "diagnostic_ir": {
                    "error_type": "model_check_error",
                    "error_subtype": "underconstrained_system",
                    "stage": "check",
                },
            },
            {
                "observed_failure_type": "simulate_error",
                "diagnostic_ir": {
                    "error_type": "simulate_error",
                    "error_subtype": "simulation_failure_unknown",
                    "stage": "simulate",
                },
            },
        ]

        picked = _pick_manifestation_live_attempt(
            attempts,
            failure_type="underconstrained_system",
            expected_stage="check",
        )

        self.assertEqual((picked.get("diagnostic_ir") or {}).get("error_type"), "model_check_error")


if __name__ == "__main__":
    unittest.main()
