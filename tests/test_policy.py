import unittest

from gateforge.policy import evaluate_policy


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


if __name__ == "__main__":
    unittest.main()
