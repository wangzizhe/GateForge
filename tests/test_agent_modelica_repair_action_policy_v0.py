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

    def test_behavioral_contract_policy_prefers_deterministic_actions(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="steady_state_target_violation",
            expected_stage="simulate",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
        )
        self.assertEqual(payload.get("channel"), "deterministic_rule_policy")
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertTrue(any("steady-state" in str(x).lower() for x in actions))

    def test_behavioral_robustness_policy_avoids_source_restore_wording(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="param_perturbation_robustness_violation",
            expected_stage="simulate",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
        )
        self.assertEqual(payload.get("channel"), "deterministic_rule_policy")
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        joined = "\n".join([str(x) for x in actions]).lower()
        self.assertIn("conservative", joined)
        self.assertNotIn("restore source", joined)

    def test_multistep_policy_switches_focus_after_stage_2_unlock(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="behavior_then_robustness",
            expected_stage="simulate",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
            multistep_context={
                "current_stage": "stage_2",
                "current_fail_bucket": "single_case_only",
            },
        )
        self.assertEqual(payload.get("channel"), "deterministic_rule_policy")
        self.assertEqual(payload.get("next_focus"), "resolve_stage_2_neighbor_robustness")
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        joined = "\n".join([str(x) for x in actions]).lower()
        self.assertIn("neighbor robustness", joined)
        self.assertNotIn("nominal behavior first", joined)


if __name__ == "__main__":
    unittest.main()
