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


if __name__ == "__main__":
    unittest.main()
