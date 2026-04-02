"""Tests for repair checkpoint module.

Pure-function tests: no Docker, LLM, OMC, or filesystem dependencies.
"""
from __future__ import annotations

import time
import unittest

from gateforge.agent_modelica_repair_checkpoint_v1 import (
    CheckpointManager,
    RepairCheckpoint,
    checkpoint_summary,
    checkpoint_text,
    make_checkpoint,
    should_capture_before,
)


# ===========================================================================
# make_checkpoint / checkpoint_text / checkpoint_summary
# ===========================================================================


class TestMakeCheckpoint(unittest.TestCase):
    def test_fields_are_stored(self) -> None:
        cp = make_checkpoint(2, "apply_repair", "model text here")
        self.assertEqual(cp.round_number, 2)
        self.assertEqual(cp.pre_operation, "apply_repair")
        self.assertEqual(cp.model_text, "model text here")

    def test_captured_at_sec_is_positive(self) -> None:
        cp = make_checkpoint(1, "apply_repair", "x")
        self.assertGreater(cp.captured_at_sec, 0)

    def test_two_checkpoints_are_ordered(self) -> None:
        cp1 = make_checkpoint(1, "apply_repair", "a")
        time.sleep(0.001)
        cp2 = make_checkpoint(2, "apply_repair", "b")
        self.assertLessEqual(cp1.captured_at_sec, cp2.captured_at_sec)

    def test_checkpoint_is_frozen(self) -> None:
        cp = make_checkpoint(1, "apply_repair", "text")
        with self.assertRaises((AttributeError, TypeError)):
            cp.model_text = "changed"  # type: ignore[misc]


class TestCheckpointText(unittest.TestCase):
    def test_returns_model_text(self) -> None:
        cp = make_checkpoint(1, "apply_repair", "some model")
        self.assertEqual(checkpoint_text(cp), "some model")

    def test_empty_text(self) -> None:
        cp = make_checkpoint(1, "apply_repair", "")
        self.assertEqual(checkpoint_text(cp), "")


class TestCheckpointSummary(unittest.TestCase):
    def test_contains_required_keys(self) -> None:
        cp = make_checkpoint(3, "restore_source", "model")
        summary = checkpoint_summary(cp)
        for key in ("round_number", "pre_operation", "model_text_len", "captured_at_sec"):
            self.assertIn(key, summary)

    def test_model_text_len_is_correct(self) -> None:
        text = "hello world"
        cp = make_checkpoint(1, "apply_repair", text)
        self.assertEqual(checkpoint_summary(cp)["model_text_len"], len(text))

    def test_round_number_matches(self) -> None:
        cp = make_checkpoint(5, "apply_repair", "x")
        self.assertEqual(checkpoint_summary(cp)["round_number"], 5)


# ===========================================================================
# should_capture_before
# ===========================================================================


class TestShouldCaptureBefore(unittest.TestCase):
    def test_apply_repair_requires_checkpoint(self) -> None:
        self.assertTrue(should_capture_before("apply_repair"))

    def test_restore_source_requires_checkpoint(self) -> None:
        self.assertTrue(should_capture_before("restore_source"))

    def test_omc_check_does_not_require_checkpoint(self) -> None:
        self.assertFalse(should_capture_before("omc_check"))

    def test_omc_simulate_does_not_require_checkpoint(self) -> None:
        self.assertFalse(should_capture_before("omc_simulate"))

    def test_replay_lookup_does_not_require_checkpoint(self) -> None:
        self.assertFalse(should_capture_before("replay_lookup"))

    def test_planner_invoke_does_not_require_checkpoint(self) -> None:
        # planner_invoke does not mutate files
        self.assertFalse(should_capture_before("planner_invoke"))

    def test_unknown_operation_is_fail_safe(self) -> None:
        # Unknown operations default to requiring a checkpoint (fail-safe)
        self.assertTrue(should_capture_before("some_unknown_future_op"))


# ===========================================================================
# CheckpointManager — basic capture and restore
# ===========================================================================


class TestCheckpointManagerBasic(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = CheckpointManager(max_retained=3)

    def test_empty_manager_has_depth_zero(self) -> None:
        self.assertEqual(self.mgr.depth, 0)

    def test_latest_returns_none_when_empty(self) -> None:
        self.assertIsNone(self.mgr.latest())

    def test_restore_latest_returns_none_when_empty(self) -> None:
        self.assertIsNone(self.mgr.restore_latest())

    def test_capture_returns_checkpoint(self) -> None:
        cp = self.mgr.capture(1, "apply_repair", "text")
        self.assertIsInstance(cp, RepairCheckpoint)
        self.assertEqual(cp.model_text, "text")

    def test_depth_increases_on_capture(self) -> None:
        self.mgr.capture(1, "apply_repair", "a")
        self.assertEqual(self.mgr.depth, 1)
        self.mgr.capture(2, "apply_repair", "b")
        self.assertEqual(self.mgr.depth, 2)

    def test_latest_returns_most_recent(self) -> None:
        self.mgr.capture(1, "apply_repair", "first")
        self.mgr.capture(2, "apply_repair", "second")
        self.assertEqual(self.mgr.latest().model_text, "second")

    def test_restore_latest_returns_most_recent_text(self) -> None:
        self.mgr.capture(1, "apply_repair", "round1_text")
        self.mgr.capture(2, "apply_repair", "round2_text")
        self.assertEqual(self.mgr.restore_latest(), "round2_text")

    def test_restore_does_not_consume_checkpoint(self) -> None:
        self.mgr.capture(1, "apply_repair", "text")
        self.mgr.restore_latest()
        self.mgr.restore_latest()  # second restore should still work
        self.assertEqual(self.mgr.restore_latest(), "text")

    def test_clear_removes_all_checkpoints(self) -> None:
        self.mgr.capture(1, "apply_repair", "a")
        self.mgr.capture(2, "apply_repair", "b")
        self.mgr.clear()
        self.assertEqual(self.mgr.depth, 0)
        self.assertIsNone(self.mgr.latest())


# ===========================================================================
# CheckpointManager — rolling window eviction
# ===========================================================================


class TestCheckpointManagerWindow(unittest.TestCase):
    def test_max_retained_is_enforced(self) -> None:
        mgr = CheckpointManager(max_retained=2)
        mgr.capture(1, "apply_repair", "a")
        mgr.capture(2, "apply_repair", "b")
        mgr.capture(3, "apply_repair", "c")
        self.assertEqual(mgr.depth, 2)

    def test_oldest_is_evicted_first(self) -> None:
        mgr = CheckpointManager(max_retained=2)
        mgr.capture(1, "apply_repair", "round1")
        mgr.capture(2, "apply_repair", "round2")
        mgr.capture(3, "apply_repair", "round3")
        # round1 should be evicted; latest should be round3
        self.assertEqual(mgr.restore_latest(), "round3")
        # round2 should still be accessible
        self.assertEqual(mgr.restore_at_round(2), "round2")
        # round1 should be gone
        self.assertIsNone(mgr.restore_at_round(1))

    def test_max_retained_one(self) -> None:
        mgr = CheckpointManager(max_retained=1)
        mgr.capture(1, "apply_repair", "first")
        mgr.capture(2, "apply_repair", "second")
        self.assertEqual(mgr.depth, 1)
        self.assertEqual(mgr.restore_latest(), "second")

    def test_invalid_max_retained_raises(self) -> None:
        with self.assertRaises(ValueError):
            CheckpointManager(max_retained=0)


# ===========================================================================
# CheckpointManager — at_round and restore_at_round
# ===========================================================================


class TestCheckpointManagerByRound(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = CheckpointManager(max_retained=5)
        self.mgr.capture(1, "apply_repair", "round1_text")
        self.mgr.capture(2, "restore_source", "round2_text")
        self.mgr.capture(3, "apply_repair", "round3_text")

    def test_at_round_returns_correct_checkpoint(self) -> None:
        cp = self.mgr.at_round(2)
        self.assertIsNotNone(cp)
        self.assertEqual(cp.model_text, "round2_text")

    def test_at_round_returns_none_for_missing_round(self) -> None:
        self.assertIsNone(self.mgr.at_round(99))

    def test_restore_at_round_returns_correct_text(self) -> None:
        self.assertEqual(self.mgr.restore_at_round(1), "round1_text")
        self.assertEqual(self.mgr.restore_at_round(3), "round3_text")

    def test_restore_at_round_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.mgr.restore_at_round(42))

    def test_at_round_returns_most_recent_if_multiple(self) -> None:
        # Two captures in round 2 — should get the second one
        self.mgr.capture(2, "apply_repair", "round2_second")
        cp = self.mgr.at_round(2)
        self.assertEqual(cp.model_text, "round2_second")


# ===========================================================================
# CheckpointManager — capture_if_needed
# ===========================================================================


class TestCaptureIfNeeded(unittest.TestCase):
    def setUp(self) -> None:
        self.mgr = CheckpointManager()

    def test_captures_for_apply_repair(self) -> None:
        cp = self.mgr.capture_if_needed(1, "apply_repair", "text")
        self.assertIsNotNone(cp)
        self.assertEqual(self.mgr.depth, 1)

    def test_captures_for_restore_source(self) -> None:
        cp = self.mgr.capture_if_needed(1, "restore_source", "text")
        self.assertIsNotNone(cp)

    def test_does_not_capture_for_omc_check(self) -> None:
        cp = self.mgr.capture_if_needed(1, "omc_check", "text")
        self.assertIsNone(cp)
        self.assertEqual(self.mgr.depth, 0)

    def test_does_not_capture_for_omc_simulate(self) -> None:
        cp = self.mgr.capture_if_needed(1, "omc_simulate", "text")
        self.assertIsNone(cp)

    def test_does_not_capture_for_replay_lookup(self) -> None:
        cp = self.mgr.capture_if_needed(1, "replay_lookup", "text")
        self.assertIsNone(cp)

    def test_does_not_capture_for_planner_invoke(self) -> None:
        cp = self.mgr.capture_if_needed(1, "planner_invoke", "text")
        self.assertIsNone(cp)

    def test_captures_for_unknown_operation(self) -> None:
        cp = self.mgr.capture_if_needed(1, "unknown_op", "text")
        self.assertIsNotNone(cp)


# ===========================================================================
# CheckpointManager — summary
# ===========================================================================


class TestCheckpointManagerSummary(unittest.TestCase):
    def test_empty_summary(self) -> None:
        mgr = CheckpointManager(max_retained=3)
        summary = mgr.summary()
        self.assertEqual(summary["depth"], 0)
        self.assertEqual(summary["max_retained"], 3)
        self.assertEqual(summary["checkpoints"], [])
        self.assertIsNone(summary["latest_round"])
        self.assertIsNone(summary["latest_operation"])

    def test_summary_after_captures(self) -> None:
        mgr = CheckpointManager(max_retained=3)
        mgr.capture(1, "apply_repair", "text1")
        mgr.capture(2, "restore_source", "text2")
        summary = mgr.summary()
        self.assertEqual(summary["depth"], 2)
        self.assertEqual(summary["latest_round"], 2)
        self.assertEqual(summary["latest_operation"], "restore_source")
        self.assertEqual(len(summary["checkpoints"]), 2)


# ===========================================================================
# Rollback scenario: end-to-end usage pattern
# ===========================================================================


class TestRollbackScenario(unittest.TestCase):
    """Simulate how a repair loop uses CheckpointManager for dirty-state recovery."""

    def test_rollback_to_pre_repair_state(self) -> None:
        mgr = CheckpointManager(max_retained=3)
        original = "model Good\n  parameter Real x = 1.0;\nend Good;"
        bad_repair = "model Good\n  // corrupted by bad LLM repair\nend Good;"

        # Round 1: capture before applying repair
        mgr.capture_if_needed(1, "apply_repair", original)
        current_text = bad_repair  # repair applied — but it made things worse

        # Round 2: realise the repair was bad, restore to pre-repair baseline
        restored = mgr.restore_at_round(1)
        self.assertIsNotNone(restored)
        current_text = restored
        self.assertEqual(current_text, original)

    def test_checkpoint_survives_multiple_bad_rounds(self) -> None:
        mgr = CheckpointManager(max_retained=3)
        clean = "clean model text"
        mgr.capture(1, "apply_repair", clean)

        # Two failed repair rounds — checkpoint from round 1 still accessible
        mgr.capture(2, "apply_repair", "partial repair v1")
        mgr.capture(3, "apply_repair", "partial repair v2")

        restored = mgr.restore_at_round(1)
        self.assertEqual(restored, clean)

    def test_checkpoint_evicted_beyond_window(self) -> None:
        mgr = CheckpointManager(max_retained=2)
        mgr.capture(1, "apply_repair", "round1")
        mgr.capture(2, "apply_repair", "round2")
        mgr.capture(3, "apply_repair", "round3")

        # Round 1 should be evicted from the 2-slot window
        self.assertIsNone(mgr.restore_at_round(1))
        self.assertIsNotNone(mgr.restore_at_round(2))


if __name__ == "__main__":
    unittest.main()
