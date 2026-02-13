import unittest

from gateforge.policy import dry_run_human_checks, evaluate_policy


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


if __name__ == "__main__":
    unittest.main()
