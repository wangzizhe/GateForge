from __future__ import annotations

import unittest

from gateforge.agent_modelica_positive_supervision_queue_v0_47_2 import (
    REQUIRED_LABEL_FIELDS,
    build_positive_supervision_queue,
)


class PositiveSupervisionQueueV0472Tests(unittest.TestCase):
    def test_queue_deduplicates_cases_and_requires_labels(self) -> None:
        summary, rows = build_positive_supervision_queue(
            examples=[
                {
                    "case_id": "case_a",
                    "mapping_gap_label": "multi_family_balanced_empty_result_stall",
                    "residual_signal_sequence": ["empty_simulation_result"],
                    "detected_candidate_families": ["pair_flow_contract"],
                    "untried_candidate_families": ["topology_rewrite"],
                },
                {"case_id": "case_a", "mapping_gap_label": "duplicate"},
            ]
        )
        self.assertEqual(summary["queue_case_count"], 1)
        self.assertEqual(rows[0]["label_status"], "missing")
        self.assertEqual(rows[0]["required_label_fields"], list(REQUIRED_LABEL_FIELDS))

    def test_queue_forbids_wrapper_patch_sources(self) -> None:
        _, rows = build_positive_supervision_queue(examples=[{"case_id": "case_a"}])
        self.assertIn("wrapper_generated_patch", rows[0]["forbidden_label_sources"])
        self.assertIn("inferred_correct_answer_from_failed_trajectory_only", rows[0]["forbidden_label_sources"])


if __name__ == "__main__":
    unittest.main()
