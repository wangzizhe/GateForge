from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_diversity_v0_20_3 import (
    analyze_round_diversity,
    run_candidate_diversity_audit,
    structural_signature,
    summarize_diversity,
)


class CandidateDiversityV0203Tests(unittest.TestCase):
    def test_structural_signature_ignores_comments(self) -> None:
        left = "model A\n  Real x;\nequation\n  x = 1;\nend A;"
        right = "model A\n  Real x; // comment\nequation\n  x = 1; // comment\nend A;"

        self.assertEqual(structural_signature(left), structural_signature(right))

    def test_analyze_round_diversity_counts_uniqueness_and_sim_rank(self) -> None:
        result = {"candidate_id": "case_a"}
        text_a = "model A\n  Real x;\nequation\n  x = 1;\nend A;"
        text_b = "model A\n  Real y;\nequation\n  y = 1;\nend A;"
        round_row = {
            "round": 1,
            "ranked": [
                {"candidate_id": 0, "patched_text": text_a},
                {"candidate_id": 1, "patched_text": text_a},
                {"candidate_id": 2, "patched_text": text_b},
            ],
            "simulate_attempts": [{"candidate_id": 2, "simulate_pass": True}],
        }

        row = analyze_round_diversity(result, round_row)

        self.assertEqual(row["candidate_count"], 3)
        self.assertEqual(row["unique_text_count"], 2)
        self.assertEqual(row["simulate_pass_rank_positions"], [2])
        self.assertFalse(row["top2_contains_simulate_pass"])
        self.assertTrue(row["top4_contains_simulate_pass"])

    def test_summarize_diversity_recommends_wider_beam_when_top2_misses(self) -> None:
        rows = [
            {
                "candidate_count": 5,
                "duplicate_text_count": 0,
                "duplicate_structural_signature_count": 0,
                "text_uniqueness_rate": 1.0,
                "structural_uniqueness_rate": 1.0,
                "simulate_pass_count": 1,
                "simulate_pass_rank_positions": [3],
                "top2_contains_simulate_pass": False,
                "top4_contains_simulate_pass": True,
            }
        ]

        summary = summarize_diversity(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(
            summary["recommendation"],
            "avoid_aggressive_pruning_use_wider_beam_or_better_selector",
        )

    def test_run_candidate_diversity_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            out = Path(tmp) / "out"
            src.mkdir()
            payload = {
                "candidate_id": "case_a",
                "rounds": [
                    {
                        "round": 1,
                        "ranked": [
                            {
                                "candidate_id": 0,
                                "patched_text": "model A\n  Real x;\nequation\n  x = 1;\nend A;",
                            }
                        ],
                        "simulate_attempts": [],
                    }
                ],
            }
            (src / "case_a_multi-c5.json").write_text(json.dumps(payload), encoding="utf-8")

            summary = run_candidate_diversity_audit(multi_c5_dir=src, out_dir=out)

            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "round_rows.json").exists())
            self.assertEqual(summary["round_count"], 1)


if __name__ == "__main__":
    unittest.main()
