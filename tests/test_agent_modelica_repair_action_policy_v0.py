import unittest

from gateforge.agent_modelica_repair_action_policy_v0 import recommend_repair_actions_v0


class AgentModelicaRepairActionPolicyV0Tests(unittest.TestCase):
    def test_underconstrained_policy_prefers_topology_restore(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="underconstrained_system",
            expected_stage="check",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
        )
        self.assertEqual(payload.get("channel"), "deterministic_rule_policy")
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertTrue(any("missing connect" in str(x).lower() for x in actions))
        self.assertTrue(any("dangling conservation path" in str(x).lower() for x in actions))
        self.assertTrue(any("checkmodel" in str(x).lower() for x in actions))

    def test_policy_prefers_deterministic_actions(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="model_check_error",
            expected_stage="check",
            diagnostic_payload={"suggested_actions": ["remove injected parser-breaking tokens before planner edits"]},
            fallback_actions=["fallback_action_1"],
        )
        self.assertEqual(payload.get("channel"), "deterministic_rule_policy")
        self.assertFalse(bool(payload.get("fallback_used")))
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertTrue(any("checkModel" in str(x) for x in actions))

    def test_policy_falls_back_when_failure_type_unknown(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="unknown_failure",
            expected_stage="simulate",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
        )
        self.assertEqual(payload.get("channel"), "fallback_planner_actions")
        self.assertTrue(bool(payload.get("fallback_used")))
        self.assertEqual(payload.get("actions"), ["fallback_action_1"])


if __name__ == "__main__":
    unittest.main()
