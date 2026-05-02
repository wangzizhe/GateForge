from __future__ import annotations

import unittest

from gateforge.agent_modelica_positive_supervision_label_template_v0_47_5 import (
    build_positive_supervision_label_template,
)


class PositiveSupervisionLabelTemplateV0475Tests(unittest.TestCase):
    def test_template_keeps_label_fields_blank_and_context_read_only(self) -> None:
        summary, rows = build_positive_supervision_label_template(
            queue_rows=[
                {
                    "case_id": "case_a",
                    "source_example_mapping_gap_label": "multi_family_balanced_empty_result_stall",
                    "residual_signal_sequence": ["empty_simulation_result"],
                    "detected_candidate_families": ["pair_flow_contract"],
                    "untried_candidate_families": ["topology_rewrite"],
                }
            ]
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(rows[0]["accepted_next_action_family"], "")
        self.assertEqual(rows[0]["minimal_contract_change_summary"], "")
        self.assertEqual(rows[0]["context"]["detected_candidate_families"], ["pair_flow_contract"])
        self.assertFalse(summary["dataset_contract"]["contains_generated_patch"])

    def test_template_reports_review_without_queue(self) -> None:
        summary, rows = build_positive_supervision_label_template(queue_rows=[])
        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
