import unittest

from gateforge.agent_modelica_resolution_attribution_v1 import (
    build_resolution_attribution,
    resolve_dominant_stage_subtype,
)


class AgentModelicaResolutionAttributionV1Tests(unittest.TestCase):
    def test_resolve_dominant_stage_subtype_prefers_most_common_attempt_value(self) -> None:
        subtype = resolve_dominant_stage_subtype(
            {
                "attempts": [
                    {"diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference"}},
                    {"diagnostic_ir": {"dominant_stage_subtype": "stage_4_initialization_singularity"}},
                    {"diagnostic_ir": {"dominant_stage_subtype": "stage_4_initialization_singularity"}},
                ]
            }
        )
        self.assertEqual(subtype, "stage_4_initialization_singularity")

    def test_build_resolution_attribution_marks_deterministic_rule_only(self) -> None:
        payload = build_resolution_attribution(
            {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "attempts": [
                    {
                        "pre_repair": {
                            "applied": True,
                            "rule_id": "rule_parse_error_pre_repair",
                            "action_key": "repair|parse_error_pre_repair|rule_engine_v1",
                        },
                        "diagnostic_ir": {"dominant_stage_subtype": "stage_1_parse_syntax"},
                    }
                ],
            }
        )
        self.assertEqual(payload["resolution_path"], "deterministic_rule_only")
        self.assertFalse(payload["planner_invoked"])
        self.assertFalse(payload["planner_used"])
        self.assertFalse(payload["planner_decisive"])
        self.assertEqual(payload["dominant_stage_subtype"], "stage_1_parse_syntax")

    def test_build_resolution_attribution_marks_rule_then_llm(self) -> None:
        payload = build_resolution_attribution(
            {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "llm_request_count_delta": 1,
                "llm_plan_generated": True,
                "attempts": [
                    {
                        "pre_repair": {
                            "applied": True,
                            "rule_id": "rule_parse_error_pre_repair",
                            "action_key": "repair|parse_error_pre_repair|rule_engine_v1",
                        },
                        "planner_experience_injection": {"enabled": True, "used": False},
                        "diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference"},
                    }
                ],
            }
        )
        self.assertEqual(payload["resolution_path"], "rule_then_llm")
        self.assertTrue(payload["planner_invoked"])
        self.assertTrue(payload["planner_used"])
        self.assertFalse(payload["planner_decisive"])

    def test_build_resolution_attribution_marks_planner_decisive_with_proxy_reason(self) -> None:
        payload = build_resolution_attribution(
            {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
                "llm_request_count_delta": 1,
                "llm_plan_generated": True,
                "llm_plan_was_decisive": True,
                "resolution_primary_contribution": "llm_first_plan",
                "planner_experience_injection": {"enabled": True, "used": True},
                "attempts": [{"diagnostic_ir": {"dominant_stage_subtype": "stage_3_behavioral_contract_semantic"}}],
            }
        )
        self.assertEqual(payload["resolution_path"], "llm_planner_assisted")
        self.assertTrue(payload["planner_decisive"])
        self.assertEqual(payload["planner_decisive_method"], "weak_supervision_proxy_heuristic")

    def test_build_resolution_attribution_uses_passed_and_hard_checks(self) -> None:
        payload = build_resolution_attribution(
            {
                "passed": True,
                "hard_checks": {
                    "check_model_pass": True,
                    "simulate_pass": True,
                    "physics_contract_pass": True,
                    "regression_pass": True,
                },
                "llm_request_count_delta": 1,
                "llm_plan_generated": True,
                "llm_plan_used": True,
            }
        )
        self.assertEqual(payload["resolution_path"], "llm_planner_assisted")
        self.assertTrue(payload["planner_invoked"])
        self.assertTrue(payload["planner_used"])


if __name__ == "__main__":
    unittest.main()
