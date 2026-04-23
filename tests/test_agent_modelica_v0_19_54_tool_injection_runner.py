from __future__ import annotations

import unittest

from scripts.run_tool_injection_trajectory_v0_19_54 import compute_summary


class TestToolInjectionRunnerSummary(unittest.TestCase):

    def test_compute_summary_uses_consistent_denominators(self) -> None:
        results = [
            {
                "candidate_id": "case_a",
                "final_status": "pass",
                "round_count": 1,
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_check_pass": True,
                        "any_simulate_pass": True,
                        "coverage_check_pass": 2,
                        "coverage_simulate_pass": 1,
                        "tool_context_enabled": True,
                        "tool_context_char_count": 100,
                        "tool_selected_variable_count": 3,
                    }
                ],
            },
            {
                "candidate_id": "case_b",
                "final_status": "fail",
                "round_count": 2,
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_check_pass": False,
                        "any_simulate_pass": False,
                        "coverage_check_pass": 0,
                        "coverage_simulate_pass": 0,
                        "tool_context_enabled": True,
                        "tool_context_char_count": 200,
                        "tool_selected_variable_count": 5,
                    },
                    {
                        "num_candidates": 5,
                        "any_check_pass": True,
                        "any_simulate_pass": False,
                        "coverage_check_pass": 1,
                        "coverage_simulate_pass": 0,
                        "tool_context_enabled": True,
                        "tool_context_char_count": 300,
                        "tool_selected_variable_count": 4,
                    },
                ],
            },
        ]

        summary = compute_summary("tool-c5", results)

        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertEqual(summary["round_count"], 3)
        self.assertEqual(summary["per_round_any_check_pass"]["count"], 2)
        self.assertEqual(summary["per_round_any_check_pass"]["denominator"], 3)
        self.assertEqual(summary["pooled_candidate_check_pass"]["count"], 3)
        self.assertEqual(summary["pooled_candidate_check_pass"]["denominator"], 15)
        self.assertEqual(summary["pooled_candidate_simulate_pass"]["count"], 1)
        self.assertEqual(summary["pooled_candidate_simulate_pass"]["denominator"], 15)
        self.assertEqual(summary["avg_tool_context_chars"], 200.0)
        self.assertEqual(summary["avg_tool_selected_variable_count"], 4.0)


if __name__ == "__main__":
    unittest.main()

