from __future__ import annotations

import unittest

from scripts.run_representation_trajectory_v0_19_56 import compute_summary


class TestRepresentationRunnerSummary(unittest.TestCase):

    def test_compute_summary(self) -> None:
        results = [
            {
                "candidate_id": "case_a",
                "final_status": "pass",
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_check_pass": True,
                        "any_simulate_pass": True,
                        "coverage_check_pass": 2,
                        "coverage_simulate_pass": 1,
                        "representation_enabled": True,
                        "representation_char_count": 120,
                        "representation_selected_variable_count": 3,
                        "representation_block_count": 2,
                    }
                ],
            },
            {
                "candidate_id": "case_b",
                "final_status": "fail",
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_check_pass": False,
                        "any_simulate_pass": False,
                        "coverage_check_pass": 0,
                        "coverage_simulate_pass": 0,
                        "representation_enabled": True,
                        "representation_char_count": 180,
                        "representation_selected_variable_count": 4,
                        "representation_block_count": 3,
                    }
                ],
            },
        ]
        summary = compute_summary("causal-c5", results)
        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertEqual(summary["per_round_any_simulate_pass"]["count"], 1)
        self.assertEqual(summary["per_round_any_simulate_pass"]["denominator"], 2)
        self.assertEqual(summary["pooled_candidate_simulate_pass"]["count"], 1)
        self.assertEqual(summary["pooled_candidate_simulate_pass"]["denominator"], 10)
        self.assertEqual(summary["avg_representation_chars"], 150.0)
        self.assertEqual(summary["avg_selected_variables"], 3.5)
        self.assertEqual(summary["avg_block_count"], 2.5)


if __name__ == "__main__":
    unittest.main()

