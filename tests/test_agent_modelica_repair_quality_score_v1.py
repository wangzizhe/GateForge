import unittest

from gateforge.agent_modelica_repair_quality_score_v1 import compute_repair_quality_breakdown


class AgentModelicaRepairQualityScoreV1Tests(unittest.TestCase):
    def test_rule_only_single_round_pass_scores_near_one(self) -> None:
        payload = {
            "check_model_pass": True,
            "simulate_pass": True,
            "physics_contract_pass": True,
            "regression_pass": True,
            "live_request_count": 0,
            "attempts": [
                {
                    "round": 1,
                    "observed_failure_type": "model_check_error",
                }
            ],
        }
        breakdown = compute_repair_quality_breakdown(payload)
        self.assertEqual(breakdown["repair_quality_score"], 1.0)

    def test_late_llm_assisted_pass_scores_midrange(self) -> None:
        payload = {
            "check_model_pass": True,
            "simulate_pass": True,
            "physics_contract_pass": True,
            "regression_pass": True,
            "live_request_count": 4,
            "attempts": [
                {"round": 1, "observed_failure_type": "model_check_error", "llm_request_count_delta": 1},
                {"round": 2, "observed_failure_type": "model_check_error", "llm_request_count_delta": 1},
                {"round": 3, "observed_failure_type": "simulate_error", "llm_request_count_delta": 1},
                {"round": 4, "observed_failure_type": "simulate_error", "llm_request_count_delta": 1},
                {"round": 5, "observed_failure_type": "none", "check_model_pass": True, "simulate_pass": True},
            ],
        }
        breakdown = compute_repair_quality_breakdown(payload)
        self.assertGreaterEqual(breakdown["repair_quality_score"], 0.5)
        self.assertLessEqual(breakdown["repair_quality_score"], 0.6)

    def test_fail_scores_zero(self) -> None:
        payload = {
            "check_model_pass": False,
            "simulate_pass": False,
            "physics_contract_pass": False,
            "regression_pass": False,
            "attempts": [
                {"round": 1, "observed_failure_type": "model_check_error"},
                {"round": 2, "observed_failure_type": "model_check_error"},
            ],
        }
        breakdown = compute_repair_quality_breakdown(payload)
        self.assertEqual(breakdown["repair_quality_score"], 0.0)

    def test_passed_flag_and_hard_checks_count_as_success(self) -> None:
        payload = {
            "passed": True,
            "hard_checks": {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
            },
            "rounds_used": 1,
            "live_request_count": 1,
        }
        breakdown = compute_repair_quality_breakdown(payload)
        self.assertTrue(breakdown["metrics"]["hard_success"])
        self.assertGreater(breakdown["repair_quality_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
