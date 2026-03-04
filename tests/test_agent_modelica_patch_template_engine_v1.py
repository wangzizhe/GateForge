import unittest

from gateforge.agent_modelica_patch_template_engine_v1 import build_patch_template


class AgentModelicaPatchTemplateEngineV1Tests(unittest.TestCase):
    def test_builds_template_for_simulate_error(self) -> None:
        payload = build_patch_template(failure_type="simulate_error", expected_stage="simulate")
        self.assertTrue(str(payload.get("template_id") or "").startswith("tpl_"))
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertGreaterEqual(len(actions), 2)

    def test_adds_focus_actions_for_matching_failure_type(self) -> None:
        payload = build_patch_template(
            failure_type="simulate_error",
            expected_stage="simulate",
            focus_queue_payload={
                "queue": [
                    {
                        "failure_type": "simulate_error",
                        "gate_break_reason": "regression_fail",
                    }
                ]
            },
        )
        self.assertGreaterEqual(int(payload.get("focus_actions_count", 0)), 1)
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertTrue(any("no-regression guard" in str(x) for x in actions))

    def test_adds_global_regression_focus_actions_across_failure_types(self) -> None:
        payload = build_patch_template(
            failure_type="model_check_error",
            expected_stage="check",
            focus_queue_payload={
                "queue": [
                    {
                        "failure_type": "simulate_error",
                        "gate_break_reason": "regression_fail",
                    }
                ]
            },
        )
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertTrue(any("runtime drift" in str(x).lower() for x in actions))


if __name__ == "__main__":
    unittest.main()
