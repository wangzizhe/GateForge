import unittest

from gateforge.agent_modelica_l4_uplift_decision_v0 import evaluate_l4_uplift_decision_v0


class AgentModelicaL4UpliftDecisionV0Tests(unittest.TestCase):
    def test_promote_from_profile_sweep_summary(self) -> None:
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
                    "delta_success_at_k_pp": 8.0,
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
                "infra_failure_count": 0,
                "l4_primary_reason": "hard_checks_pass",
            },
            main_weekly_summary={
                "recommendation": "promote",
                "recommendation_reason": "two_week_consecutive_pass",
            },
            night_sweep_summary={},
            night_l5_summary={"infra_failure_count": 0},
            night_weekly_summary={},
        )
        self.assertEqual(summary.get("decision"), "promote")
        self.assertEqual(summary.get("primary_reason"), "none")
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(summary.get("main_compare_source_kind"), "profile_sweep")
        self.assertEqual(summary.get("main_recommended_profile"), "score_v1b")

    def test_baseline_too_weak_skips_delta_reason(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 33.33,
                "baseline_meets_minimum": False,
                "baseline_has_headroom": True,
                "baseline_eligible_for_uplift": False,
                "baseline_in_target_range": False,
            },
            main_sweep_summary={
                "recommended_profile_result": {
                    "profile": "score_v1",
                    "delta_success_at_k_pp": 0.0,
                    "delta_regression_fail_rate_pp": 0.0,
                    "delta_physics_fail_rate_pp": 0.0,
                    "infra_failure_count_on": 0,
                    "l4_primary_reason_on": "no_progress_window",
                }
            },
            main_l5_summary={"gate_result": "FAIL", "infra_failure_count": 1},
            main_weekly_summary={"recommendation": "hold", "recommendation_reason": "infra_failure_count_not_zero"},
            night_sweep_summary={},
            night_l5_summary={"infra_failure_count": 0},
            night_weekly_summary={},
        )
        reasons = set(summary.get("reasons") or [])
        self.assertIn("infra", reasons)
        self.assertIn("baseline_too_weak", reasons)
        self.assertNotIn("delta_below_threshold", reasons)
        self.assertEqual(summary.get("primary_reason"), "infra")
        self.assertEqual(summary.get("decision"), "hold")

    def test_baseline_saturated_skips_delta_reason(self) -> None:
        summary = evaluate_l4_uplift_decision_v0(
            challenge_summary={
                "baseline_off_success_at_k_pct": 100.0,
                "baseline_meets_minimum": True,
                "baseline_has_headroom": False,
                "baseline_eligible_for_uplift": False,
                "baseline_in_target_range": True,
            },
            main_sweep_summary={
                "recommended_profile_result": {
                    "profile": "score_v1",
                    "delta_success_at_k_pp": 0.0,
                    "delta_regression_fail_rate_pp": 0.0,
                    "delta_physics_fail_rate_pp": 0.0,
                    "infra_failure_count_on": 0,
                    "l4_primary_reason_on": "hard_checks_pass",
                }
            },
            main_l5_summary={"gate_result": "PASS", "infra_failure_count": 0},
            main_weekly_summary={"recommendation": "hold", "recommendation_reason": "threshold_not_met"},
            night_sweep_summary={},
            night_l5_summary={"infra_failure_count": 0},
            night_weekly_summary={},
        )
        reasons = set(summary.get("reasons") or [])
        self.assertIn("baseline_saturated_no_headroom", reasons)
        self.assertNotIn("delta_below_threshold", reasons)
        self.assertEqual(summary.get("primary_reason"), "baseline_saturated_no_headroom")
        self.assertEqual(summary.get("decision"), "hold")


if __name__ == "__main__":
    unittest.main()
