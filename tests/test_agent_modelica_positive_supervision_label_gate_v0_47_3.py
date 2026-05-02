from __future__ import annotations

import unittest

from gateforge.agent_modelica_positive_supervision_label_gate_v0_47_3 import (
    build_positive_supervision_label_gate,
    validate_positive_supervision_label,
)


class PositiveSupervisionLabelGateV0473Tests(unittest.TestCase):
    def test_rejects_missing_and_forbidden_labels(self) -> None:
        status, issues = validate_positive_supervision_label(
            {
                "case_id": "case_a",
                "label_source": "inferred_correct_answer_from_failed_trajectory_only",
                "contains_wrapper_repair": True,
            }
        )
        self.assertEqual(status, "REVIEW")
        self.assertIn("label_source_not_allowed", issues)
        self.assertIn("contains_wrapper_repair", issues)
        self.assertIn("missing_accepted_next_action_family", issues)

    def test_accepts_complete_source_backed_label(self) -> None:
        status, issues = validate_positive_supervision_label(
            {
                "case_id": "case_a",
                "label_source": "source_backed_reference_model_diff",
                "accepted_next_action_family": "contract_delta_minimal",
                "minimal_contract_change_summary": "Move the missing flow contract into the concrete implementation.",
                "why_failed_candidate_family_was_wrong": "The failed candidate changed topology instead of contract.",
                "verification_requirement": "check_model and simulate must pass.",
            }
        )
        self.assertEqual(status, "PASS")
        self.assertEqual(issues, [])

    def test_gate_blocks_when_labels_are_missing(self) -> None:
        summary = build_positive_supervision_label_gate(
            queue_rows=[{"case_id": "case_a"}, {"case_id": "case_b"}],
            labels=[],
        )
        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(summary["label_status_counts"], {"MISSING": 2})
        self.assertFalse(summary["admission_contract"]["labels_may_be_used_for_training"])


if __name__ == "__main__":
    unittest.main()
