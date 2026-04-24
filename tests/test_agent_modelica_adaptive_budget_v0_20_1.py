from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_adaptive_budget_v0_20_1 import (
    choose_adaptive_budget,
    replay_case_budget,
    run_adaptive_budget_replay,
    summarize_budget_replay,
    visible_ranked_candidates,
    visible_simulate_attempts,
)


class AdaptiveBudgetV0201Tests(unittest.TestCase):
    def test_choose_adaptive_budget_uses_prior_round_only(self) -> None:
        self.assertEqual(choose_adaptive_budget([]), 3)
        self.assertEqual(choose_adaptive_budget([{"any_check_pass": False}]), 5)
        self.assertEqual(
            choose_adaptive_budget([{"any_check_pass": True, "any_simulate_pass": False}]),
            5,
        )
        self.assertEqual(
            choose_adaptive_budget([{"any_check_pass": True, "any_simulate_pass": True}]),
            3,
        )
        self.assertEqual(choose_adaptive_budget([{"advance": "stalled_no_change"}]), 5)

    def test_visible_candidates_respect_budget_by_generation_id(self) -> None:
        round_row = {
            "ranked": [
                {"candidate_id": 4, "check_pass": True},
                {"candidate_id": 0, "check_pass": False},
                {"candidate_id": 2, "check_pass": True},
            ],
            "simulate_attempts": [
                {"candidate_id": 4, "simulate_pass": True},
                {"candidate_id": 2, "simulate_pass": False},
            ],
        }

        self.assertEqual([row["candidate_id"] for row in visible_ranked_candidates(round_row, 3)], [0, 2])
        self.assertEqual([row["candidate_id"] for row in visible_simulate_attempts(round_row, 3)], [2])

    def test_replay_case_budget_counts_adaptive_visibility(self) -> None:
        result = {
            "candidate_id": "case_a",
            "final_status": "pass",
            "rounds": [
                {
                    "round": 1,
                    "num_candidates": 5,
                    "ranked": [
                        {"candidate_id": 4, "check_pass": True},
                        {"candidate_id": 0, "check_pass": False},
                    ],
                    "simulate_attempts": [{"candidate_id": 4, "simulate_pass": True}],
                    "coverage_check_pass": 1,
                    "coverage_simulate_pass": 1,
                    "any_check_pass": True,
                    "any_simulate_pass": True,
                },
                {
                    "round": 2,
                    "num_candidates": 5,
                    "ranked": [{"candidate_id": 0, "check_pass": True}],
                    "simulate_attempts": [{"candidate_id": 0, "simulate_pass": True}],
                    "coverage_check_pass": 1,
                    "coverage_simulate_pass": 1,
                    "any_check_pass": True,
                    "any_simulate_pass": True,
                },
            ],
        }

        replay = replay_case_budget(result)

        self.assertEqual(replay["fixed_candidate_count"], 10)
        self.assertEqual(replay["adaptive_candidate_count"], 6)
        self.assertEqual(replay["adaptive_any_simulate_rounds"], 1)

    def test_summarize_budget_replay_reports_recommendation(self) -> None:
        rows = [
            {
                "round_count": 2,
                "fixed_candidate_count": 10,
                "adaptive_candidate_count": 6,
                "fixed_any_check_rounds": 2,
                "adaptive_any_check_rounds": 2,
                "fixed_any_simulate_rounds": 1,
                "adaptive_any_simulate_rounds": 1,
            }
        ]

        summary = summarize_budget_replay(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["candidate_savings"], 4)
        self.assertEqual(summary["promotion_recommendation"], "eligible_for_live_arm")

    def test_run_adaptive_budget_replay_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            out = Path(tmp) / "out"
            src.mkdir()
            payload = {
                "candidate_id": "case_a",
                "final_status": "fail",
                "rounds": [
                    {
                        "round": 1,
                        "num_candidates": 5,
                        "ranked": [{"candidate_id": 0, "check_pass": False}],
                        "simulate_attempts": [],
                        "coverage_check_pass": 0,
                        "coverage_simulate_pass": 0,
                        "any_check_pass": False,
                        "any_simulate_pass": False,
                    }
                ],
            }
            (src / "case_a_multi-c5.json").write_text(json.dumps(payload), encoding="utf-8")

            summary = run_adaptive_budget_replay(multi_c5_dir=src, out_dir=out)

            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "replay_rows.json").exists())
            self.assertEqual(summary["case_count"], 1)


if __name__ == "__main__":
    unittest.main()
