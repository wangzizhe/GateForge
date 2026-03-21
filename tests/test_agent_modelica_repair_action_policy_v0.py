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
        self.assertTrue(bool(payload.get("plan_generated")))
        self.assertTrue(bool(payload.get("plan_followed")))
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        joined = "\n".join([str(x) for x in actions]).lower()
        self.assertIn("neighbor robustness", joined)
        self.assertNotIn("nominal behavior first", joined)
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        self.assertEqual(plan.get("plan_stage"), "stage_2")
        self.assertIn("second", str(plan.get("plan_goal") or "").lower())

    def test_multistep_policy_generates_stage_1_unlock_plan(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="stability_then_behavior",
            expected_stage="simulate",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
            multistep_context={
                "current_stage": "stage_1",
                "current_fail_bucket": "stability_margin_miss",
            },
        )
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        self.assertEqual(plan.get("plan_stage"), "stage_1")
        self.assertEqual(payload.get("next_focus"), "unlock_stage_2_behavior_gate")
        self.assertIn("unlock", str(plan.get("plan_goal") or "").lower())
        self.assertTrue(any("stability" in str(x).lower() for x in (plan.get("plan_actions") or [])))

    def test_multistep_policy_rejects_stage_1_suggestions_after_stage_2_unlock(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="switch_then_recovery",
            expected_stage="simulate",
            diagnostic_payload={"suggested_actions": ["revisit switch timing unlock step before anything else"]},
            fallback_actions=[],
            multistep_context={
                "current_stage": "stage_2",
                "current_fail_bucket": "post_switch_recovery_miss",
            },
        )
        self.assertTrue(bool(payload.get("plan_conflict_rejected")))
        self.assertGreater(int(payload.get("plan_conflict_rejected_count") or 0), 0)
        actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
        self.assertFalse(any("unlock step" in str(x).lower() for x in actions))

    def test_multistep_policy_generates_trap_branch_plan(self) -> None:
        payload = recommend_repair_actions_v0(
            failure_type="switch_then_recovery",
            expected_stage="simulate",
            diagnostic_payload={},
            fallback_actions=["fallback_action_1"],
            multistep_context={
                "current_stage": "stage_2",
                "current_fail_bucket": "single_case_only",
                "stage_2_branch": "recovery_overfit_trap",
                "preferred_stage_2_branch": "post_switch_recovery_branch",
                "trap_branch": True,
            },
        )
        self.assertEqual(payload.get("next_focus"), "escape_trap_branch_recovery_overfit")
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        self.assertEqual(plan.get("branch_mode"), "trap")
        self.assertEqual(plan.get("current_branch"), "recovery_overfit_trap")
        self.assertEqual(plan.get("preferred_branch"), "post_switch_recovery_branch")
        self.assertIn("escape", str(plan.get("branch_plan_goal") or "").lower())
        self.assertTrue(any("trap" in str(x).lower() for x in (plan.get("branch_plan_actions") or [])))


if __name__ == "__main__":
    unittest.main()
