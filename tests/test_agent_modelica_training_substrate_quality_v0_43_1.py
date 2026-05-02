from __future__ import annotations

import unittest

from gateforge.agent_modelica_training_substrate_quality_audit_v0_43_1 import (
    build_training_substrate_quality_audit,
    classify_training_record_quality,
)


class TrainingSubstrateQualityV0431Tests(unittest.TestCase):
    def test_classifies_no_submit_after_model_check_pass(self) -> None:
        quality = classify_training_record_quality(
            {
                "failure_category": "no_final_submission",
                "tool_call_sequence": ["check_model"],
                "tool_result_signal_sequence": ["model_check_pass"],
            }
        )
        self.assertEqual(quality, "no_submit_after_model_check_pass")

    def test_classifies_no_submit_after_simulation_probe(self) -> None:
        quality = classify_training_record_quality(
            {
                "failure_category": "no_final_submission",
                "tool_call_sequence": ["check_model", "simulate_model"],
                "tool_result_signal_sequence": ["model_check_pass"],
            }
        )
        self.assertEqual(quality, "no_submit_after_simulation_probe")

    def test_summary_marks_submit_decision_dataset_ready(self) -> None:
        summary = build_training_substrate_quality_audit(
            [
                {
                    "case_id": "case",
                    "failure_category": "no_final_submission",
                    "tool_call_sequence": ["check_model"],
                    "tool_result_signal_sequence": ["model_check_pass"],
                }
            ]
        )
        self.assertEqual(summary["training_readiness"], "submit_decision_dataset_ready")
        self.assertTrue(summary["all_failures_are_no_final_submission"])


if __name__ == "__main__":
    unittest.main()
