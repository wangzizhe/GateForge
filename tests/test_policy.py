import unittest

from gateforge.policy import dry_run_human_checks, evaluate_policy, load_policy, resolve_policy_path, run_required_human_checks


class PolicyTests(unittest.TestCase):
    def test_policy_pass_on_empty_reasons(self) -> None:
        policy = {
            "critical_reason_prefixes": ["strict_"],
            "needs_review_reason_prefixes": ["runtime_regression"],
            "fail_on_needs_review_risk_levels": ["high"],
            "fail_on_unknown_reasons": True,
        }
        result = evaluate_policy([], "low", policy)
        self.assertEqual(result["policy_decision"], "PASS")

    def test_policy_needs_review_for_low_runtime_regression(self) -> None:
        policy = {
            "critical_reason_prefixes": ["strict_"],
            "needs_review_reason_prefixes": ["runtime_regression"],
            "fail_on_needs_review_risk_levels": ["high"],
            "fail_on_unknown_reasons": True,
        }
        result = evaluate_policy(["runtime_regression:1.2s>1.0s"], "low", policy)
        self.assertEqual(result["policy_decision"], "NEEDS_REVIEW")

    def test_policy_fail_for_high_runtime_regression(self) -> None:
        policy = {
            "critical_reason_prefixes": ["strict_"],
            "needs_review_reason_prefixes": ["runtime_regression"],
            "fail_on_needs_review_risk_levels": ["high"],
            "fail_on_unknown_reasons": True,
        }
        result = evaluate_policy(["runtime_regression:1.2s>1.0s"], "high", policy)
        self.assertEqual(result["policy_decision"], "FAIL")

    def test_policy_force_needs_review_prefix_overrides_high_risk_fail(self) -> None:
        policy = {
            "critical_reason_prefixes": ["strict_"],
            "needs_review_reason_prefixes": ["change_requires_human_review"],
            "always_needs_review_reason_prefixes": ["change_requires_human_review"],
            "fail_on_needs_review_risk_levels": ["high"],
            "fail_on_unknown_reasons": True,
        }
        result = evaluate_policy(["change_requires_human_review"], "high", policy)
        self.assertEqual(result["policy_decision"], "NEEDS_REVIEW")

    def test_dry_run_human_checks_default_fallback(self) -> None:
        checks = dry_run_human_checks(policy={}, risk_level="high", has_change_set=True)
        self.assertTrue(any("rollback" in c.lower() for c in checks))
        self.assertTrue(any("change-set" in c.lower() for c in checks))

    def test_dry_run_human_checks_custom_templates(self) -> None:
        policy = {
            "dry_run_human_checks": {
                "base": ["base-a", "base-b"],
                "medium_extra": ["med-a"],
                "high_extra": ["high-a"],
                "changeset_extra": ["cs-a"],
            }
        }
        checks = dry_run_human_checks(policy=policy, risk_level="high", has_change_set=True)
        self.assertEqual(checks, ["base-a", "base-b", "med-a", "high-a", "cs-a"])

    def test_run_required_human_checks_from_templates(self) -> None:
        policy = {
            "required_human_checks": {
                "by_reason_prefix": {
                    "runtime_regression": ["runtime-check"],
                    "candidate_gate_not_pass": ["gate-check"],
                },
                "by_failure_type": {
                    "docker_error": ["docker-check"],
                },
                "fallback": ["fallback-check"],
            }
        }
        checks = run_required_human_checks(
            policy=policy,
            policy_decision="FAIL",
            policy_reasons=["runtime_regression:1.0>0.5", "candidate_gate_not_pass"],
            candidate_failure_type="docker_error",
        )
        self.assertEqual(checks, ["runtime-check", "gate-check", "docker-check"])

    def test_run_required_human_checks_fallback(self) -> None:
        checks = run_required_human_checks(
            policy={},
            policy_decision="FAIL",
            policy_reasons=["unknown_reason"],
            candidate_failure_type=None,
        )
        self.assertEqual(len(checks), 1)
        self.assertIn("human review required", checks[0].lower())

    def test_default_policy_performance_regression_low_needs_review(self) -> None:
        policy = load_policy()
        result = evaluate_policy(["performance_regression_detected"], "low", policy)
        self.assertEqual(result["policy_decision"], "NEEDS_REVIEW")

    def test_default_policy_event_explosion_fail(self) -> None:
        policy = load_policy()
        result = evaluate_policy(["event_explosion_detected"], "low", policy)
        self.assertEqual(result["policy_decision"], "FAIL")

    def test_industrial_profile_runtime_regression_medium_fail(self) -> None:
        policy = load_policy("policies/profiles/industrial_strict_v0.json")
        result = evaluate_policy(["runtime_regression:1.2s>1.0s"], "medium", policy)
        self.assertEqual(result["policy_decision"], "FAIL")

    def test_resolve_policy_path_from_profile(self) -> None:
        resolved = resolve_policy_path(policy_profile="industrial_strict_v0")
        self.assertEqual(resolved, "policies/profiles/industrial_strict_v0.json")

    def test_resolve_policy_path_rejects_both_path_and_profile(self) -> None:
        with self.assertRaises(ValueError):
            resolve_policy_path(
                policy_path="policies/default_policy.json",
                policy_profile="industrial_strict_v0",
            )


if __name__ == "__main__":
    unittest.main()
