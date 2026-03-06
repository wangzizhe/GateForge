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
        self.assertTrue(any("event count" in str(x).lower() for x in actions))

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

    def test_adds_semantic_specific_regression_focus_actions(self) -> None:
        payload = build_patch_template(
            failure_type="semantic_regression",
            expected_stage="simulate",
            focus_queue_payload={
                "queue": [
                    {
                        "failure_type": "semantic_regression",
                        "gate_break_reason": "regression_fail",
                    }
                ]
            },
        )
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertTrue(any("overshoot" in str(x).lower() for x in actions))

    def test_merges_adaptation_actions(self) -> None:
        payload = build_patch_template(
            failure_type="simulate_error",
            expected_stage="simulate",
            adaptations_payload={
                "failure_types": {
                    "simulate_error": {
                        "actions": [
                            "reuse successful initialization seed from memory",
                            "stabilize start values and initial equations near t=0",
                        ]
                    }
                }
            },
        )
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertIn("reuse successful initialization seed from memory", actions)
        self.assertEqual(actions.count("stabilize start values and initial equations near t=0"), 1)
        self.assertEqual(int(payload.get("adaptation_actions_count", 0)), 2)


if __name__ == "__main__":
    unittest.main()
