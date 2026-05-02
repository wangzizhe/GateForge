from __future__ import annotations

import unittest

from gateforge.agent_modelica_residual_candidate_supervision_audit_v0_47_1 import (
    build_residual_candidate_supervision_audit,
)


class ResidualCandidateSupervisionAuditV0471Tests(unittest.TestCase):
    def test_negative_only_examples_are_not_repair_policy_training_ready(self) -> None:
        summary = build_residual_candidate_supervision_audit(
            examples=[
                {
                    "case_id": "case_a",
                    "final_verdict": "FAILED",
                    "submitted": False,
                    "mapping_gap_label": "residual_misread_as_compiler_limitation",
                    "input_contract": {"contains_reference_solution": False, "contains_wrapper_repair": False},
                }
            ]
        )
        self.assertEqual(
            summary["trainability_status"],
            "negative_trajectory_schema_ready_positive_supervision_missing",
        )
        self.assertFalse(summary["dataset_contract"]["can_train_repair_policy"])
        self.assertTrue(summary["dataset_contract"]["can_train_failure_classifier"])

    def test_positive_supervision_can_make_schema_training_ready(self) -> None:
        examples = []
        for idx in range(4):
            examples.append(
                {
                    "case_id": f"case_{idx}",
                    "final_verdict": "FAILED",
                    "submitted": False,
                    "accepted_next_action": "contract_delta_minimal",
                    "mapping_gap_label": "contract_flow_ownership_mapping_gap",
                    "input_contract": {"contains_reference_solution": False, "contains_wrapper_repair": False},
                }
            )
        summary = build_residual_candidate_supervision_audit(examples=examples)
        self.assertEqual(summary["trainability_status"], "training_ready")
        self.assertTrue(summary["dataset_contract"]["can_train_repair_policy"])


if __name__ == "__main__":
    unittest.main()
