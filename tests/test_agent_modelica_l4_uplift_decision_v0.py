import unittest

from gateforge.agent_modelica_l4_uplift_decision_v0 import evaluate_l4_uplift_decision_v0


class AgentModelicaL4UpliftDecisionV0Tests(unittest.TestCase):
    def test_promote_in_delta_mode_when_delta_and_quality_pass(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 72.0,
                "baseline_meets_minimum": True,
                "baseline_has_headroom": True,
                "baseline_eligible_for_uplift": True,
                "baseline_in_target_range": True,
            },
            main_sweep_summary={
                "status": "PASS",
                "recommended_profile": "score_v1b",
                "recommended_profile_result": {
                    "profile": "score_v1b",
                    "success_at_k_pct_on": 88.0,
                    "success_at_k_pct_off": 72.0,
                    "delta_success_at_k_pp": 16.0,
                    "delta_regression_fail_rate_pp": 0.0,
                    "delta_physics_fail_rate_pp": 0.0,
                    "infra_failure_count_on": 0,
                    "no_progress_rate_pct_on": 10.0,
                    "llm_fallback_rate_pct_on": 5.0,
                    "l4_primary_reason_on": "hard_checks_pass",
                    "reason_distribution_on": {"hard_checks_pass": 4},
                },
            },
            main_l5_summary={
                "gate_result": "PASS",
                "status": "PASS",
                "success_at_k_pct": 88.0,
                "non_regression_ok": True,
                "infra_failure_count": 0,
                "l4_primary_reason": "hard_checks_pass",
            },
            main_weekly_summary={
                "recommendation": "promote",
                "recommendation_reason": "two_week_consecutive_pass",
            },
            night_sweep_summary={"status": "PASS"},
            night_l5_summary={"infra_failure_count": 0, "status": "PASS"},
            night_weekly_summary={"recommendation": "hold", "recommendation_reason": "insufficient_consecutive_history"},
        )
        self.assertEqual(summary.get("decision"), "promote")
        self.assertEqual(summary.get("primary_reason"), "none")
        self.assertEqual(summary.get("acceptance_mode"), "delta_uplift")

    def test_baseline_too_weak_short_circuits(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 33.33,
                "baseline_meets_minimum": False,
                "baseline_has_headroom": True,
                "baseline_eligible_for_uplift": False,
                "baseline_in_target_range": False,
            },
            main_sweep_summary={},
            main_l5_summary={},
            main_weekly_summary={},
            night_sweep_summary={},
            night_l5_summary={},
            night_weekly_summary={},
        )
        self.assertEqual(summary.get("decision"), "hold")
        self.assertEqual(summary.get("primary_reason"), "baseline_too_weak")
        self.assertEqual(summary.get("acceptance_mode"), "delta_uplift")

    def test_absolute_mode_promotes_when_threshold_met_and_non_regressing(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 100.0,
                "baseline_meets_minimum": True,
                "baseline_has_headroom": False,
                "baseline_eligible_for_uplift": False,
                "baseline_in_target_range": True,
            },
            main_sweep_summary={
                "status": "PASS",
                "recommended_profile": "score_v1",
                "recommended_profile_result": {
                    "profile": "score_v1",
                    "success_at_k_pct_on": 100.0,
                    "success_at_k_pct_off": 100.0,
                    "delta_success_at_k_pp": 0.0,
                    "delta_regression_fail_rate_pp": 0.0,
                    "delta_physics_fail_rate_pp": 0.0,
                    "infra_failure_count_on": 0,
                    "l4_primary_reason_on": "hard_checks_pass",
                },
            },
            main_l5_summary={
                "gate_result": "PASS",
                "status": "PASS",
                "success_at_k_pct": 100.0,
                "non_regression_ok": True,
                "infra_failure_count": 0,
                "l4_primary_reason": "hard_checks_pass",
            },
            main_weekly_summary={"recommendation": "hold", "recommendation_reason": "insufficient_consecutive_history"},
            night_sweep_summary={"status": "PASS"},
            night_l5_summary={"infra_failure_count": 0, "status": "PASS"},
            night_weekly_summary={"recommendation": "hold", "recommendation_reason": "insufficient_consecutive_history"},
            absolute_success_target_pct=85.0,
        )
        self.assertEqual(summary.get("decision"), "promote")
        self.assertEqual(summary.get("primary_reason"), "none")
        self.assertEqual(summary.get("acceptance_mode"), "absolute_non_regression")

    def test_absolute_mode_holds_when_absolute_success_is_below_threshold(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 100.0,
                "baseline_meets_minimum": True,
                "baseline_has_headroom": False,
                "baseline_eligible_for_uplift": False,
                "baseline_in_target_range": True,
            },
            main_sweep_summary={"status": "PASS", "recommended_profile_result": {"success_at_k_pct_on": 80.0, "success_at_k_pct_off": 100.0}},
            main_l5_summary={
                "gate_result": "FAIL",
                "status": "FAIL",
                "success_at_k_pct": 80.0,
                "non_regression_ok": False,
                "infra_failure_count": 0,
            },
            main_weekly_summary={"recommendation": "hold", "recommendation_reason": "absolute_success_below_threshold"},
            night_sweep_summary={"status": "PASS"},
            night_l5_summary={"infra_failure_count": 0, "status": "PASS"},
            night_weekly_summary={"recommendation": "hold", "recommendation_reason": "insufficient_consecutive_history"},
            absolute_success_target_pct=85.0,
        )
        self.assertEqual(summary.get("decision"), "hold")
        self.assertEqual(summary.get("primary_reason"), "absolute_success_below_threshold")

    def test_absolute_mode_holds_when_non_regressing_check_fails(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 100.0,
                "baseline_meets_minimum": True,
                "baseline_has_headroom": False,
                "baseline_eligible_for_uplift": False,
                "baseline_in_target_range": True,
            },
            main_sweep_summary={
                "status": "PASS",
                "recommended_profile_result": {
                    "success_at_k_pct_on": 99.0,
                    "success_at_k_pct_off": 100.0,
                    "delta_success_at_k_pp": -1.0,
                    "delta_regression_fail_rate_pp": 0.0,
                    "delta_physics_fail_rate_pp": 0.0,
                },
            },
            main_l5_summary={
                "gate_result": "FAIL",
                "status": "FAIL",
                "success_at_k_pct": 99.0,
                "non_regression_ok": False,
                "infra_failure_count": 0,
            },
            main_weekly_summary={"recommendation": "hold", "recommendation_reason": "non_regression_failed"},
            night_sweep_summary={"status": "PASS"},
            night_l5_summary={"infra_failure_count": 0, "status": "PASS"},
            night_weekly_summary={"recommendation": "hold", "recommendation_reason": "insufficient_consecutive_history"},
        )
        self.assertEqual(summary.get("decision"), "hold")
        self.assertEqual(summary.get("primary_reason"), "quality_regression")


if __name__ == "__main__":
    unittest.main()
