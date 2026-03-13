import unittest

from gateforge.agent_modelica_run_contract_v1 import _should_refresh_diagnostic_ir


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


if __name__ == "__main__":
    unittest.main()
