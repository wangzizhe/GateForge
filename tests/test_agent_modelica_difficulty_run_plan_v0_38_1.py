from __future__ import annotations

import unittest

from gateforge.agent_modelica_difficulty_run_plan_v0_38_1 import build_difficulty_run_plan


class DifficultyRunPlanV0381Tests(unittest.TestCase):
    def test_plan_prioritizes_formal_hard_and_known_prior(self) -> None:
        summary = build_difficulty_run_plan(
            {
                "results": [
                    {"case_id": "hard", "family": "f", "difficulty_bucket": "hard_negative"},
                    {"case_id": "prior", "family": "f", "difficulty_bucket": "known_hard_prior"},
                    {"case_id": "new", "family": "g", "difficulty_bucket": "needs_baseline"},
                    {"case_id": "bad", "family": "g", "difficulty_bucket": "invalid"},
                ]
            },
            max_needs_baseline=1,
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["planned_case_count"], 3)
        self.assertEqual(summary["invalid_excluded_case_ids"], ["bad"])
        self.assertEqual(
            [row["run_reason"] for row in summary["planned_cases"]],
            [
                "confirm_formal_hard_negative",
                "convert_known_hard_prior_to_repeatability",
                "initial_baseline_difficulty_probe",
            ],
        )

    def test_plan_limits_needs_baseline_slice(self) -> None:
        summary = build_difficulty_run_plan(
            {
                "results": [
                    {"case_id": f"case_{idx}", "family": "f", "difficulty_bucket": "needs_baseline"}
                    for idx in range(5)
                ]
            },
            max_needs_baseline=2,
        )
        self.assertEqual(summary["planned_case_count"], 2)
        self.assertEqual(summary["needs_baseline_total_count"], 5)
        self.assertEqual(summary["needs_baseline_selected_count"], 2)

    def test_run_contract_is_base_tool_use_without_wrapper_repair(self) -> None:
        summary = build_difficulty_run_plan({"results": [{"case_id": "a", "family": "f", "difficulty_bucket": "needs_baseline"}]})
        self.assertEqual(summary["run_contract"]["tool_profile"], "base")
        self.assertFalse(summary["run_contract"]["wrapper_repair_allowed"])


if __name__ == "__main__":
    unittest.main()
