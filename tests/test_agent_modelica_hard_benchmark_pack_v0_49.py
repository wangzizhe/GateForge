from __future__ import annotations

import unittest

from gateforge.agent_modelica_hard_benchmark_closeout_v0_49_4 import build_hard_benchmark_closeout
from gateforge.agent_modelica_hard_benchmark_pack_v0_49_2 import build_hard_benchmark_pack
from gateforge.agent_modelica_hard_candidate_registry_promote_v0_49_0 import (
    build_hard_candidate_registry_promotion,
    infer_family,
)


class HardBenchmarkPackV049Tests(unittest.TestCase):
    def test_promotes_hard_candidates_to_registry_seeds(self) -> None:
        summary, seeds = build_hard_candidate_registry_promotion(
            difficulty_summary={
                "results": [
                    {"case_id": "sem_32_four_segment_adapter_cross_node", "difficulty_bucket": "hard_negative_candidate"},
                    {"case_id": "sem_28_four_branch_probe_bus", "difficulty_bucket": "unstable"},
                ]
            },
            admission_summary={"results": [{"case_id": "sem_32_four_segment_adapter_cross_node", "admission_status": "admitted_under_determined"}]},
        )
        self.assertEqual(summary["promoted_seed_count"], 1)
        self.assertEqual(seeds[0]["known_hard_for"], ["provider-env / model-env / base tool-use / 32k"] * 2)

    def test_family_inference_splits_probe_and_adapter(self) -> None:
        self.assertEqual(infer_family("sem_32_four_segment_adapter_cross_node"), "arrayed_adapter_cross_node")
        self.assertEqual(infer_family("sem_30_wide_probe_bus"), "arrayed_connector_probe_bus")

    def test_pack_merges_existing_and_new_hard_cases(self) -> None:
        summary = build_hard_benchmark_pack(
            calibration_summary={"formal_hard_negative_case_ids": ["old_case"]},
            repeatability_registry=[
                {"case_id": "new_case", "registry_status": "repeatable_candidate"},
                {"case_id": "pending_case", "registry_status": "admitted"},
            ],
            difficulty_summary={"results": [{"case_id": "unstable_case", "difficulty_bucket": "unstable"}]},
        )
        self.assertEqual(summary["hard_pack_count"], 2)
        self.assertEqual(summary["new_hard_count"], 1)
        self.assertEqual(summary["unstable_case_ids"], ["unstable_case"])

    def test_closeout_reports_ready_pack(self) -> None:
        summary = build_hard_benchmark_closeout(
            pack={"status": "PASS", "conclusion_allowed": True, "hard_pack_count": 15, "new_hard_count": 6},
            promotion={"promoted_seed_count": 6},
            repeatability={"repeatability_pass_count": 6},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["decision"], "v0_49_benchmark_pack_ready")


if __name__ == "__main__":
    unittest.main()
