import unittest

from gateforge.agent_modelica_error_action_mapper_v1 import map_error_to_actions


class AgentModelicaErrorActionMapperV1Tests(unittest.TestCase):
    def test_maps_compile_error_to_action(self) -> None:
        payload = map_error_to_actions(
            error_message="Error: undefined symbol x in equation section",
            failure_type="model_check_error",
        )
        self.assertGreaterEqual(int(payload.get("mapped_count", 0)), 1)
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
        self.assertIn("declare_missing_symbol", tags)

    def test_maps_regression_signals_to_targeted_actions(self) -> None:
        payload = map_error_to_actions(
            error_message="runtime_regression:1.45 overshoot_regression_detected settling_time_regression_detected",
            failure_type="semantic_regression",
        )
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertIn("guard_runtime_regression", tags)
        self.assertIn("repair_overshoot_regression", tags)
        self.assertIn("repair_settling_time_regression", tags)
        self.assertTrue(any("runtime budget" in str(x).lower() for x in actions))

    def test_maps_equation_balance_errors(self) -> None:
        payload = map_error_to_actions(
            error_message="Model is underdetermined: too few equations",
            failure_type="model_check_error",
        )
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
        self.assertIn("fix_equation_balance", tags)


if __name__ == "__main__":
    unittest.main()
