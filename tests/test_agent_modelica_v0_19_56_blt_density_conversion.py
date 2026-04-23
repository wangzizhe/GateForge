import tempfile
import unittest
from pathlib import Path

from scripts.analyze_blt_density_conversion_v0_19_56 import (
    build_analysis,
    classify_blt_conversion,
    round_conversion_record,
    sim_pass_candidate_ids,
    write_outputs,
)


class BltDensityConversionAnalysisTests(unittest.TestCase):
    def test_sim_pass_candidate_ids_extracts_only_simulate_pass(self):
        record = {
            "simulate_attempts": [
                {"candidate_id": 0, "simulate_pass": False},
                {"candidate_id": 1, "simulate_pass": True},
                {"candidate_id": 2, "simulate_pass": True},
            ]
        }

        self.assertEqual(sim_pass_candidate_ids(record), [1, 2])

    def test_round_conversion_marks_chosen_simulate_pass(self):
        record = {
            "round": 2,
            "num_candidates": 5,
            "coverage_check_pass": 3,
            "simulate_attempts": [
                {"candidate_id": 1, "simulate_pass": True},
            ],
            "chosen_candidate_id": 1,
            "advance": "pass",
        }

        converted = round_conversion_record(
            candidate_id="case_a", mode="blt-c5", round_record=record
        )

        self.assertEqual(converted["simulate_pass_candidate_ids"], [1])
        self.assertTrue(converted["chosen_is_simulate_pass"])

    def test_classify_blt_conversion_no_good_candidate(self):
        case = {
            "final_status": "fail",
            "rounds": [
                {"simulate_pass_count": 0, "chosen_is_simulate_pass": False},
                {"simulate_pass_count": 0, "chosen_is_simulate_pass": False},
            ],
        }

        self.assertEqual(classify_blt_conversion(case), "no_good_candidate_emerged")

    def test_classify_blt_conversion_selection_miss(self):
        case = {
            "final_status": "fail",
            "rounds": [
                {"simulate_pass_count": 1, "chosen_is_simulate_pass": False},
            ],
        }

        self.assertEqual(classify_blt_conversion(case), "selection_miss")

    def test_build_analysis_summarizes_real_v0_19_56_artifacts(self):
        trajectory_dir = Path("artifacts/representation_trajectory_v0_19_56")
        if not trajectory_dir.exists():
            self.skipTest("v0.19.56 representation artifacts are not available")

        analysis = build_analysis(trajectory_dir)

        self.assertEqual(analysis["case_count"], 8)
        self.assertEqual(
            analysis["totals"]["baseline_simulate_pass_candidates"], 6
        )
        self.assertEqual(analysis["totals"]["blt_simulate_pass_candidates"], 12)
        self.assertEqual(analysis["totals"]["delta"], 6)
        self.assertEqual(
            analysis["totals"]["blt_failed_with_simulate_pass_candidate_count"], 0
        )

    def test_write_outputs_creates_summary_report_and_tables(self):
        analysis = {
            "version": "v0.19.56",
            "source_artifact": "source",
            "modes": ["baseline-c5", "blt-c5"],
            "case_count": 1,
            "totals": {
                "baseline_simulate_pass_candidates": 0,
                "blt_simulate_pass_candidates": 1,
                "delta": 1,
                "positive_delta_case_count": 1,
                "flat_delta_case_count": 0,
                "negative_delta_case_count": 0,
                "blt_failed_case_count": 0,
                "blt_failed_with_simulate_pass_candidate_count": 0,
            },
            "conversion_counts": {"converted_to_pass": 1},
            "case_comparisons": [
                {
                    "candidate_id": "case_a",
                    "baseline_final_status": "fail",
                    "blt_final_status": "pass",
                    "baseline_simulate_pass_candidate_total": 0,
                    "blt_simulate_pass_candidate_total": 1,
                    "simulate_pass_candidate_delta": 1,
                    "baseline_rounds_with_simulate_pass": 0,
                    "blt_rounds_with_simulate_pass": 1,
                    "conversion_class": "converted_to_pass",
                }
            ],
            "round_records": [
                {
                    "candidate_id": "case_a",
                    "mode": "blt-c5",
                    "round": 1,
                    "num_candidates": 5,
                    "check_pass_count": 1,
                    "simulate_pass_count": 1,
                    "simulate_pass_candidate_ids": [0],
                    "chosen_candidate_id": 0,
                    "chosen_is_simulate_pass": True,
                    "advance": "pass",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_outputs(analysis, out_dir)

            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())
            self.assertTrue((out_dir / "round_records.csv").exists())
            self.assertTrue((out_dir / "case_comparisons.csv").exists())


if __name__ == "__main__":
    unittest.main()
