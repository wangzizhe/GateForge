"""Tests for repair rollback policy.

Pure-function tests: no Docker, LLM, OMC, or filesystem dependencies.
"""
from __future__ import annotations

import unittest

from gateforge.agent_modelica_repair_rollback_policy_v1 import (
    ROLLBACK_REASON_CHECK_REGRESSION,
    ROLLBACK_REASON_CONTRACT_REGRESSION,
    ROLLBACK_REASON_NONE,
    ROLLBACK_REASON_SCENARIO_REGRESSION,
    ROLLBACK_REASON_SIMULATE_REGRESSION,
    rollback_reason,
    should_rollback,
)


# ===========================================================================
# No rollback needed
# ===========================================================================


class TestNoRollback(unittest.TestCase):
    def test_all_ok_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=True,
            pre_contract_pass=True, post_contract_pass=True,
        ))

    def test_improvement_no_rollback(self) -> None:
        # Was broken, now fixed — definitely no rollback
        self.assertFalse(should_rollback(
            pre_check_ok=False, post_check_ok=True,
            pre_simulate_ok=False, post_simulate_ok=True,
            pre_contract_pass=False, post_contract_pass=True,
        ))

    def test_check_stays_failing_no_rollback(self) -> None:
        # Already broken before, still broken — not a regression
        self.assertFalse(should_rollback(
            pre_check_ok=False, post_check_ok=False,
        ))

    def test_simulate_stays_failing_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=False, post_simulate_ok=False,
        ))

    def test_contract_none_both_no_rollback(self) -> None:
        # Contract not evaluated on either side — not a regression
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=None, post_contract_pass=None,
        ))

    def test_contract_none_pre_no_rollback(self) -> None:
        # Was not evaluated before, now fails — not a regression (can't compare)
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=None, post_contract_pass=False,
        ))

    def test_scenario_count_equal_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_scenario_pass_count=3, post_scenario_pass_count=3,
        ))

    def test_scenario_count_improved_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_scenario_pass_count=2, post_scenario_pass_count=4,
        ))

    def test_scenario_count_none_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_scenario_pass_count=None, post_scenario_pass_count=None,
        ))

    def test_reason_is_none_when_no_rollback(self) -> None:
        reason = rollback_reason(pre_check_ok=True, post_check_ok=True)
        self.assertEqual(reason, ROLLBACK_REASON_NONE)


# ===========================================================================
# Check regression
# ===========================================================================


class TestCheckRegression(unittest.TestCase):
    def test_check_ok_drops_triggers_rollback(self) -> None:
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=False,
        ))

    def test_reason_is_check_regression(self) -> None:
        reason = rollback_reason(pre_check_ok=True, post_check_ok=False)
        self.assertEqual(reason, ROLLBACK_REASON_CHECK_REGRESSION)

    def test_check_regression_overrides_simulate_improvement(self) -> None:
        # Check dropped even though simulate improved — still rollback
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=False,
            pre_simulate_ok=False, post_simulate_ok=True,
        ))

    def test_reason_is_check_regression_not_simulate(self) -> None:
        # Check fires first in the priority order
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=False,
            pre_simulate_ok=False, post_simulate_ok=True,
        )
        self.assertEqual(reason, ROLLBACK_REASON_CHECK_REGRESSION)


# ===========================================================================
# Simulate regression
# ===========================================================================


class TestSimulateRegression(unittest.TestCase):
    def test_simulate_ok_drops_triggers_rollback(self) -> None:
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=False,
        ))

    def test_reason_is_simulate_regression(self) -> None:
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=False,
        )
        self.assertEqual(reason, ROLLBACK_REASON_SIMULATE_REGRESSION)

    def test_simulate_regression_independent_of_check(self) -> None:
        # compile still passes, simulate drops — rollback
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=False,
            pre_contract_pass=True, post_contract_pass=True,
        ))

    def test_simulate_default_none_no_regression(self) -> None:
        # Default simulate_ok is None — check is skipped, no rollback
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
        ))

    def test_simulate_both_none_no_rollback(self) -> None:
        # Neither side evaluated — cannot determine regression, skip check
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=None, post_simulate_ok=None,
        ))

    def test_simulate_pre_none_post_false_no_rollback(self) -> None:
        # Pre not evaluated, post failed — not determinable as regression
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=None, post_simulate_ok=False,
        ))

    def test_simulate_pre_true_post_none_no_rollback(self) -> None:
        # Post not evaluated (e.g. skipped) — cannot confirm regression
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=None,
        ))

    def test_simulate_was_false_now_false_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=False, post_simulate_ok=False,
        ))


# ===========================================================================
# Contract regression
# ===========================================================================


class TestContractRegression(unittest.TestCase):
    def test_contract_pass_drops_triggers_rollback(self) -> None:
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=True,
            pre_contract_pass=True, post_contract_pass=False,
        ))

    def test_reason_is_contract_regression(self) -> None:
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=True,
            pre_contract_pass=True, post_contract_pass=False,
        )
        self.assertEqual(reason, ROLLBACK_REASON_CONTRACT_REGRESSION)

    def test_contract_false_to_false_no_rollback(self) -> None:
        # Was already failing — not a regression
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=False, post_contract_pass=False,
        ))

    def test_contract_false_to_true_no_rollback(self) -> None:
        # Improvement
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=False, post_contract_pass=True,
        ))


# ===========================================================================
# Scenario count regression
# ===========================================================================


class TestScenarioRegression(unittest.TestCase):
    def test_scenario_count_drops_triggers_rollback(self) -> None:
        # Both have aggregate contract_pass=False, but scenario count dropped
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=False, post_contract_pass=False,
            pre_scenario_pass_count=3, post_scenario_pass_count=1,
        ))

    def test_reason_is_scenario_regression(self) -> None:
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=False, post_contract_pass=False,
            pre_scenario_pass_count=3, post_scenario_pass_count=2,
        )
        self.assertEqual(reason, ROLLBACK_REASON_SCENARIO_REGRESSION)

    def test_scenario_partial_degradation_caught(self) -> None:
        # This is the key case: aggregate pass stays False, but count drops
        self.assertTrue(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_contract_pass=False, post_contract_pass=False,
            pre_scenario_pass_count=2, post_scenario_pass_count=1,
        ))

    def test_scenario_count_zero_to_zero_no_rollback(self) -> None:
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_scenario_pass_count=0, post_scenario_pass_count=0,
        ))

    def test_scenario_count_partial_none_no_rollback(self) -> None:
        # Only one side available — cannot compare
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_scenario_pass_count=3, post_scenario_pass_count=None,
        ))
        self.assertFalse(should_rollback(
            pre_check_ok=True, post_check_ok=True,
            pre_scenario_pass_count=None, post_scenario_pass_count=1,
        ))


# ===========================================================================
# Priority ordering
# ===========================================================================


class TestPriorityOrdering(unittest.TestCase):
    def test_check_fires_before_simulate(self) -> None:
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=False,
            pre_simulate_ok=True, post_simulate_ok=False,
        )
        self.assertEqual(reason, ROLLBACK_REASON_CHECK_REGRESSION)

    def test_simulate_fires_before_contract(self) -> None:
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=False,
            pre_contract_pass=True, post_contract_pass=False,
        )
        self.assertEqual(reason, ROLLBACK_REASON_SIMULATE_REGRESSION)

    def test_contract_fires_before_scenario(self) -> None:
        reason = rollback_reason(
            pre_check_ok=True, post_check_ok=True,
            pre_simulate_ok=True, post_simulate_ok=True,
            pre_contract_pass=True, post_contract_pass=False,
            pre_scenario_pass_count=5, post_scenario_pass_count=0,
        )
        self.assertEqual(reason, ROLLBACK_REASON_CONTRACT_REGRESSION)


# ===========================================================================
# Public constants
# ===========================================================================


class TestPublicConstants(unittest.TestCase):
    def test_constants_are_strings(self) -> None:
        for c in (
            ROLLBACK_REASON_NONE,
            ROLLBACK_REASON_CHECK_REGRESSION,
            ROLLBACK_REASON_SIMULATE_REGRESSION,
            ROLLBACK_REASON_CONTRACT_REGRESSION,
            ROLLBACK_REASON_SCENARIO_REGRESSION,
        ):
            self.assertIsInstance(c, str)

    def test_none_constant_is_none_string(self) -> None:
        self.assertEqual(ROLLBACK_REASON_NONE, "none")

    def test_all_constants_distinct(self) -> None:
        constants = [
            ROLLBACK_REASON_NONE,
            ROLLBACK_REASON_CHECK_REGRESSION,
            ROLLBACK_REASON_SIMULATE_REGRESSION,
            ROLLBACK_REASON_CONTRACT_REGRESSION,
            ROLLBACK_REASON_SCENARIO_REGRESSION,
        ]
        self.assertEqual(len(constants), len(set(constants)))


if __name__ == "__main__":
    unittest.main()
