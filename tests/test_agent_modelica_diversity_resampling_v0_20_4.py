from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_diversity_resampling_v0_20_4 import (
    build_resampling_row,
    build_safe_resampling_note,
    classify_resampling_need,
    run_diversity_resampling_profile,
    summarize_resampling,
)


class DiversityResamplingV0204Tests(unittest.TestCase):
    def test_classify_resampling_need_prioritizes_low_structural_diversity(self) -> None:
        self.assertEqual(
            classify_resampling_need(
                structural_uniqueness_rate=0.4,
                text_uniqueness_rate=1.0,
                simulate_pass_count=1,
            ),
            "diversity_resample",
        )
        self.assertEqual(
            classify_resampling_need(
                structural_uniqueness_rate=0.9,
                text_uniqueness_rate=0.5,
                simulate_pass_count=0,
            ),
            "failure_aware_resample",
        )
        self.assertEqual(
            classify_resampling_need(
                structural_uniqueness_rate=0.9,
                text_uniqueness_rate=1.0,
                simulate_pass_count=1,
            ),
            "keep_standard_sampling",
        )

    def test_safe_note_avoids_case_specific_terms(self) -> None:
        note = build_safe_resampling_note({"recommendation": "diversity_resample"})

        self.assertIn("distinct repair hypotheses", note)
        self.assertNotIn("candidate_id", note)
        self.assertNotIn("model family", note)
        self.assertNotIn("variable", note.lower())

    def test_build_resampling_row_marks_low_diversity(self) -> None:
        text = "model A\n  Real x;\nequation\n  x = 1;\nend A;"
        result = {"candidate_id": "case_a"}
        round_row = {
            "round": 1,
            "ranked": [
                {"candidate_id": 0, "patched_text": text},
                {"candidate_id": 1, "patched_text": text},
                {"candidate_id": 2, "patched_text": text},
            ],
            "simulate_attempts": [],
        }

        row = build_resampling_row(result, round_row)

        self.assertEqual(row["recommendation"], "diversity_resample")
        self.assertLess(row["structural_uniqueness_rate"], 0.75)

    def test_summarize_resampling_reports_rates(self) -> None:
        rows = [
            {"recommendation": "diversity_resample", "structural_uniqueness_rate": 0.2},
            {"recommendation": "keep_standard_sampling", "structural_uniqueness_rate": 1.0},
        ]

        summary = summarize_resampling(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["diversity_resample_count"], 1)
        self.assertEqual(summary["diversity_resample_rate"], 0.5)

    def test_run_diversity_resampling_profile_writes_outputs(self) -> None:
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

            summary = run_diversity_resampling_profile(multi_c5_dir=src, out_dir=out)

            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "resampling_rows.json").exists())
            self.assertEqual(summary["round_count"], 1)


if __name__ == "__main__":
    unittest.main()
