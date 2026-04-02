from __future__ import annotations

import unittest

from gateforge.agent_modelica_prompt_input_hygiene_v1 import (
    default_context_truncation_summary,
    truncate_planner_experience_context,
    truncate_replan_context_for_prompt,
)


class TestDefaultContextTruncationSummary(unittest.TestCase):
    def test_returns_fresh_default_dict(self) -> None:
        left = default_context_truncation_summary()
        right = default_context_truncation_summary()
        self.assertEqual(left["truncation_reason"], "none")
        self.assertIsNot(left, right)


class TestTruncatePlannerExperienceContext(unittest.TestCase):
    def test_marks_outer_truncation_when_prompt_context_is_long(self) -> None:
        context = {
            "used": True,
            "truncated": False,
            "prompt_context_text": "\n".join(f"hint {i}" for i in range(250)),
        }
        updated, summary = truncate_planner_experience_context(context)
        self.assertTrue(updated["truncated"])
        self.assertTrue(summary["was_truncated"])
        self.assertEqual(summary["truncation_reason"], "line_cap")
        self.assertIn("planner_experience_context", updated["prompt_context_text"])
        self.assertIn("line_cap", updated["prompt_context_text"])

    def test_preserves_existing_truncated_flag(self) -> None:
        context = {
            "used": True,
            "truncated": True,
            "prompt_context_text": "short",
        }
        updated, summary = truncate_planner_experience_context(context)
        self.assertTrue(updated["truncated"])
        self.assertFalse(summary["was_truncated"])


class TestTruncateReplanContextForPrompt(unittest.TestCase):
    def test_caps_previous_candidate_lists(self) -> None:
        context = {
            "previous_candidate_parameters": [f"p{i}" for i in range(10)],
            "previous_candidate_value_directions": [f"d{i}" for i in range(9)],
        }
        updated, summary = truncate_replan_context_for_prompt(context)
        self.assertEqual(len(updated["previous_candidate_parameters"]), 6)
        self.assertEqual(len(updated["previous_candidate_value_directions"]), 6)
        self.assertTrue(summary["previous_candidate_parameters"]["was_truncated"])
        self.assertTrue(summary["previous_candidate_value_directions"]["was_truncated"])
        self.assertTrue(summary["was_truncated"])

    def test_caps_guided_search_observation_lists(self) -> None:
        context = {
            "guided_search_observation": {
                "guided_search_bucket_sequence": [f"bucket_{i}" for i in range(8)],
                "no_progress_buckets": [f"np_{i}" for i in range(7)],
                "abandoned_branches": [f"branch_{i}" for i in range(9)],
                "branch_frozen_by_budget": [f"frozen_{i}" for i in range(8)],
            }
        }
        updated, summary = truncate_replan_context_for_prompt(context)
        guided = updated["guided_search_observation"]
        self.assertEqual(len(guided["guided_search_bucket_sequence"]), 6)
        self.assertEqual(len(guided["no_progress_buckets"]), 6)
        self.assertEqual(len(guided["abandoned_branches"]), 6)
        self.assertEqual(len(guided["branch_frozen_by_budget"]), 6)
        self.assertTrue(summary["guided_search_observation"]["guided_search_bucket_sequence"]["was_truncated"])
        self.assertTrue(summary["was_truncated"])

    def test_leaves_short_lists_unchanged(self) -> None:
        context = {
            "previous_candidate_parameters": ["p0", "p1"],
            "guided_search_observation": {
                "guided_search_bucket_sequence": ["resolution"],
            },
        }
        updated, summary = truncate_replan_context_for_prompt(context)
        self.assertEqual(updated["previous_candidate_parameters"], ["p0", "p1"])
        self.assertEqual(updated["guided_search_observation"]["guided_search_bucket_sequence"], ["resolution"])
        self.assertFalse(summary["was_truncated"])


if __name__ == "__main__":
    unittest.main()
