import tempfile
import unittest
from pathlib import Path

from scripts.analyze_representation_effect_stratification_v0_19_56 import (
    build_analysis,
    infer_model_family,
    route_label,
    summarize_case_result,
    treatment_effect,
    write_outputs,
)


class RepresentationStratificationTests(unittest.TestCase):
    def test_infer_model_family_from_candidate_id(self):
        self.assertEqual(
            infer_model_family("v01945_ThermalZone_v0_pp_c1_c2_pv_phi1"),
            "ThermalZone",
        )
        self.assertEqual(infer_model_family("unknown_case"), "unknown")

    def test_summarize_case_result_counts_candidates(self):
        result = {
            "candidate_id": "v01945_ThermalZone_v0_pp_c1_c2_pv_phi1",
            "mode": "blt-c5",
            "final_status": "pass",
            "final_round": 2,
            "round_count": 2,
            "rounds": [
                {
                    "coverage_check_pass": 1,
                    "coverage_simulate_pass": 0,
                    "advance": "check_pass_sim_fail_all",
                    "representation_enabled": True,
                    "representation_char_count": 100,
                    "representation_selected_variable_count": 2,
                    "representation_block_count": 3,
                },
                {
                    "coverage_check_pass": 2,
                    "coverage_simulate_pass": 1,
                    "advance": "pass",
                    "representation_enabled": True,
                    "representation_char_count": 200,
                    "representation_selected_variable_count": 4,
                    "representation_block_count": 5,
                },
            ],
        }

        summary = summarize_case_result(result)

        self.assertTrue(summary["passed"])
        self.assertEqual(summary["check_pass_candidate_total"], 3)
        self.assertEqual(summary["simulate_pass_candidate_total"], 1)
        self.assertEqual(summary["rounds_with_simulate_pass"], 1)
        self.assertEqual(summary["avg_representation_chars"], 150)

    def test_treatment_effect_labels_rescue_and_regression(self):
        baseline_fail = {"passed": False, "final_round": 0}
        baseline_pass = {"passed": True, "final_round": 2}
        treatment_pass = {"passed": True, "final_round": 1}
        treatment_fail = {"passed": False, "final_round": 0}

        self.assertEqual(treatment_effect(baseline_fail, treatment_pass), "rescued")
        self.assertEqual(treatment_effect(baseline_pass, treatment_fail), "regressed")
        self.assertEqual(
            treatment_effect(baseline_pass, treatment_pass), "preserved_pass_faster"
        )

    def test_route_label_prefers_baseline_when_it_passes(self):
        case_modes = {
            "baseline-c5": {"passed": True, "simulate_pass_candidate_total": 1},
            "causal-c5": {"passed": True, "simulate_pass_candidate_total": 3},
            "blt-c5": {"passed": False, "simulate_pass_candidate_total": 0},
        }

        self.assertEqual(route_label(case_modes), "baseline-c5")

    def test_build_analysis_summarizes_real_v0_19_56_artifacts(self):
        trajectory_dir = Path("artifacts/representation_trajectory_v0_19_56")
        if not trajectory_dir.exists():
            self.skipTest("v0.19.56 representation artifacts are not available")

        analysis = build_analysis(trajectory_dir)

        self.assertEqual(analysis["case_count"], 8)
        self.assertEqual(analysis["mode_pass_counts"]["baseline-c5"], 4)
        self.assertEqual(analysis["mode_pass_counts"]["causal-c5"], 3)
        self.assertEqual(analysis["mode_pass_counts"]["blt-c5"], 4)
        self.assertEqual(analysis["union_pass_count"], 7)

    def test_write_outputs_creates_report_and_tables(self):
        analysis = {
            "version": "v0.19.56",
            "source_artifact": "source",
            "case_count": 1,
            "mode_pass_counts": {
                "baseline-c5": 0,
                "causal-c5": 1,
                "blt-c5": 0,
            },
            "union_pass_count": 1,
            "union_pass_rate": 1.0,
            "route_counts": {"causal-c5": 1},
            "effect_counts": {"causal-c5": {"rescued": 1}},
            "case_rows": [
                {
                    "candidate_id": "case_a",
                    "model_family": "ThermalZone",
                    "baseline_status": "fail",
                    "causal_status": "pass",
                    "blt_status": "fail",
                    "baseline_sim_candidates": 0,
                    "causal_sim_candidates": 1,
                    "blt_sim_candidates": 0,
                    "baseline_round_count": 4,
                    "causal_round_count": 2,
                    "blt_round_count": 4,
                    "route_label": "causal-c5",
                    "any_mode_passed": True,
                }
            ],
            "effect_rows": [
                {
                    "candidate_id": "case_a",
                    "model_family": "ThermalZone",
                    "mode": "causal-c5",
                    "effect_vs_baseline": "rescued",
                    "sim_candidate_delta": 1,
                }
            ],
            "family_rows": [
                {
                    "model_family": "ThermalZone",
                    "case_count": 1,
                    "baseline_pass": 0,
                    "causal_pass": 1,
                    "blt_pass": 0,
                    "union_pass": 1,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_outputs(analysis, out_dir)

            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())
            self.assertTrue((out_dir / "case_stratification.csv").exists())
            self.assertTrue((out_dir / "effect_vs_baseline.csv").exists())
            self.assertTrue((out_dir / "family_stratification.csv").exists())


if __name__ == "__main__":
    unittest.main()
