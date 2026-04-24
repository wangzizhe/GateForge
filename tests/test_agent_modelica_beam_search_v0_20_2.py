from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_beam_search_v0_20_2 import (
    replay_case_beam,
    run_beam_replay,
    select_beam_nodes,
    summarize_beam_replay,
)


class BeamSearchV0202Tests(unittest.TestCase):
    def test_select_beam_nodes_prefers_ranked_order_and_marks_sim_pass(self) -> None:
        round_row = {
            "ranked": [
                {"candidate_id": 3, "patched_text": "model A end A;", "score": 10, "check_pass": False},
                {"candidate_id": 1, "patched_text": "model B end B;", "score": 9, "check_pass": True},
                {"candidate_id": 2, "patched_text": "", "score": 8, "check_pass": True},
            ],
            "simulate_attempts": [{"candidate_id": 1, "simulate_pass": True}],
        }

        selected = select_beam_nodes(round_row, beam_width=2)

        self.assertEqual([row["candidate_id"] for row in selected], [3, 1])
        self.assertFalse(selected[0]["simulate_pass"])
        self.assertTrue(selected[1]["simulate_pass"])

    def test_replay_case_beam_counts_selected_retention(self) -> None:
        result = {
            "candidate_id": "case_a",
            "final_status": "pass",
            "rounds": [
                {
                    "round": 1,
                    "num_candidates": 5,
                    "ranked": [
                        {"candidate_id": 4, "patched_text": "x", "check_pass": True, "score": 10},
                        {"candidate_id": 0, "patched_text": "y", "check_pass": False, "score": 8},
                        {"candidate_id": 1, "patched_text": "z", "check_pass": True, "score": 7},
                    ],
                    "simulate_attempts": [{"candidate_id": 4, "simulate_pass": True}],
                    "coverage_check_pass": 2,
                    "coverage_simulate_pass": 1,
                }
            ],
        }

        replay = replay_case_beam(result, beam_width=2)

        self.assertEqual(replay["fixed_candidate_count"], 5)
        self.assertEqual(replay["selected_node_count"], 2)
        self.assertEqual(replay["selected_simulate_pass_nodes"], 1)

    def test_summarize_beam_replay_reports_recommendation(self) -> None:
        rows = [
            {
                "fixed_candidate_count": 10,
                "selected_node_count": 4,
                "fixed_check_pass_nodes": 2,
                "selected_check_pass_nodes": 2,
                "fixed_simulate_pass_nodes": 1,
                "selected_simulate_pass_nodes": 1,
            }
        ]

        summary = summarize_beam_replay(rows, beam_width=2)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["node_savings"], 6)
        self.assertEqual(summary["promotion_recommendation"], "eligible_for_live_tree_search_arm")

    def test_run_beam_replay_writes_outputs(self) -> None:
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
                        "ranked": [{"candidate_id": 0, "patched_text": "x", "check_pass": False}],
                        "simulate_attempts": [],
                        "coverage_check_pass": 0,
                        "coverage_simulate_pass": 0,
                    }
                ],
            }
            (src / "case_a_multi-c5.json").write_text(json.dumps(payload), encoding="utf-8")

            summary = run_beam_replay(multi_c5_dir=src, out_dir=out, beam_width=2)

            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "replay_rows.json").exists())
            self.assertEqual(summary["case_count"], 1)


if __name__ == "__main__":
    unittest.main()
