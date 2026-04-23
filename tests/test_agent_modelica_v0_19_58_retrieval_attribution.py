import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "analyze_retrieval_attribution_v0_19_58.py"
)
SPEC = importlib.util.spec_from_file_location(
    "analyze_retrieval_attribution_v0_19_58",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AgentModelicaV01958RetrievalAttributionTests(unittest.TestCase):
    def test_classify_outcome_transition(self) -> None:
        self.assertEqual(
            MODULE.classify_outcome_transition("pass", "fail"),
            "retrieval_regression",
        )
        self.assertEqual(
            MODULE.classify_outcome_transition("fail", "pass"),
            "retrieval_uplift",
        )
        self.assertEqual(
            MODULE.classify_outcome_transition("pass", "pass"),
            "both_pass",
        )

    def test_first_divergence_round_detects_round_one_change(self) -> None:
        baseline = [
            {
                "advance": "pass",
                "chosen_candidate_id": 2,
                "coverage_check_pass": 2,
                "coverage_simulate_pass": 2,
            }
        ]
        retrieval = [
            {
                "advance": "advanced_with_top",
                "chosen_candidate_id": 1,
                "coverage_check_pass": 0,
                "coverage_simulate_pass": 0,
            }
        ]
        self.assertEqual(MODULE.first_divergence_round(baseline, retrieval), 1)

    def test_infer_mechanism_marks_regression_when_retrieval_loses_check_pass(self) -> None:
        mechanism, rationale = MODULE.infer_mechanism(
            candidate_id="v01945_HydroTurbineGov_v0_pp_at_dturb_pv_q_nl",
            baseline_payload={
                "final_status": "pass",
                "rounds": [{"coverage_check_pass": 2}],
            },
            retrieval_payload={
                "final_status": "fail",
                "rounds": [{"coverage_check_pass": 0}, {"coverage_check_pass": 0}],
            },
            retrieval_hit_infos=[],
        )
        self.assertEqual(mechanism, "retrieval_diluted_current_omc_signal")
        self.assertIn("check-pass", rationale)

    def test_infer_mechanism_marks_uplift_when_retrieval_improves_search(self) -> None:
        mechanism, _ = MODULE.infer_mechanism(
            candidate_id="v01945_SyncMachineSimplified_v0_pp_efd_set_id_set_pv_xadifd",
            baseline_payload={
                "final_status": "fail",
                "rounds": [{"coverage_check_pass": 0}, {"coverage_check_pass": 0}],
            },
            retrieval_payload={
                "final_status": "pass",
                "rounds": [{"coverage_check_pass": 0}, {"coverage_check_pass": 4}],
            },
            retrieval_hit_infos=[],
        )
        self.assertEqual(mechanism, "retrieval_helped_search_direction")

    def test_aggregate_summary_counts_transitions(self) -> None:
        summary = MODULE.aggregate_summary(
            [
                {
                    "dataset": "hot",
                    "transition": "retrieval_regression",
                    "mechanism": "retrieval_diluted_current_omc_signal",
                },
                {
                    "dataset": "cold",
                    "transition": "retrieval_uplift",
                    "mechanism": "retrieval_helped_search_direction",
                },
            ]
        )
        self.assertEqual(summary["case_count"], 2)
        self.assertEqual(summary["transition_counts"]["retrieval_regression"], 1)
        self.assertEqual(summary["transition_counts"]["retrieval_uplift"], 1)
        self.assertEqual(
            summary["by_dataset"]["hot"]["transition_counts"]["retrieval_regression"],
            1,
        )
        self.assertEqual(
            summary["by_dataset"]["cold"]["mechanism_counts"]["retrieval_helped_search_direction"],
            1,
        )

    def test_infer_mechanism_ignores_unknown_model_family_for_cross_family_hits(self) -> None:
        mechanism, _ = MODULE.infer_mechanism(
            candidate_id="v01945_ExciterAVR_v0_pp_e1_e2_pv_se_efd",
            baseline_payload={
                "final_status": "pass",
                "rounds": [{"coverage_check_pass": 0}],
            },
            retrieval_payload={
                "final_status": "fail",
                "rounds": [{"coverage_check_pass": 0}],
            },
            retrieval_hit_infos=[
                {"model_family": "unknown"},
                {"model_family": ""},
            ],
        )
        self.assertEqual(mechanism, "retrieval_added_unhelpful_context")


if __name__ == "__main__":
    unittest.main()
