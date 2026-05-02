from __future__ import annotations

import unittest

from gateforge.agent_modelica_hard_core_expansion_slice_v0_39_0 import (
    build_hard_core_expansion_slice,
    score_expansion_candidate,
)


class HardCoreExpansionSliceV0390Tests(unittest.TestCase):
    def test_scores_only_same_family_needs_baseline(self) -> None:
        self.assertGreaterEqual(
            score_expansion_candidate(
                {
                    "case_id": "sem_21_arrayed_mixed_probe_contract",
                    "family": "arrayed_connector_flow",
                    "difficulty_bucket": "needs_baseline",
                }
            ),
            0,
        )
        self.assertEqual(
            score_expansion_candidate(
                {
                    "case_id": "sem_20_arrayed_adapter_cross_node",
                    "family": "arrayed_connector_flow",
                    "difficulty_bucket": "needs_baseline",
                }
            ),
            -1,
        )
        self.assertEqual(
            score_expansion_candidate(
                {
                    "case_id": "other",
                    "family": "parameter_binding",
                    "difficulty_bucket": "needs_baseline",
                }
            ),
            -1,
        )

    def test_build_slice_prefers_semantic_neighbors(self) -> None:
        summary = build_hard_core_expansion_slice(
            {
                "version": "v0.fixture",
                "results": [
                    {
                        "case_id": "r_05_phantom_msl",
                        "family": "arrayed_connector_flow",
                        "difficulty_bucket": "needs_baseline",
                    },
                    {
                        "case_id": "sem_21_arrayed_mixed_probe_contract",
                        "family": "arrayed_connector_flow",
                        "difficulty_bucket": "needs_baseline",
                    },
                ],
            },
            limit=1,
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["selected_case_ids"], ["sem_21_arrayed_mixed_probe_contract"])
        self.assertEqual(summary["runner_contract"]["wrapper_repair"], "forbidden")


if __name__ == "__main__":
    unittest.main()
