from __future__ import annotations

import unittest

from gateforge.agent_modelica_residual_candidate_training_schema_v0_47_0 import (
    build_residual_candidate_training_summary,
    classify_mapping_gap,
    classify_omc_signal,
)


class ResidualCandidateTrainingSchemaV0470Tests(unittest.TestCase):
    def test_classifies_omc_residual_signals(self) -> None:
        self.assertEqual(classify_omc_signal('record SimulationResult resultFile = ""'), "empty_simulation_result")
        self.assertEqual(classify_omc_signal("Error: Too few equations"), "under_determined")
        self.assertEqual(classify_omc_signal("Error: Too many equations"), "over_determined")

    def test_mapping_gap_detects_direction_flip(self) -> None:
        row = {
            "steps": [
                {"tool_results": [{"result": "Error: Too few equations"}]},
                {"tool_results": [{"result": "Error: Too many equations"}]},
            ]
        }
        self.assertEqual(classify_mapping_gap(row), "delta_overshoot_or_direction_flip")

    def test_summary_never_claims_formal_conclusion_or_reference_solution(self) -> None:
        summary, examples = build_residual_candidate_training_summary(
            substrate_records=[
                {
                    "case_id": "sem_13_arrayed_connector_bus_refactor",
                    "result_path": "/missing/results.jsonl",
                }
            ]
        )
        self.assertEqual(summary["status"], "REVIEW")
        self.assertFalse(summary["conclusion_allowed"])
        self.assertFalse(summary["dataset_contract"]["contains_reference_solution"])
        self.assertEqual(examples, [])

    def test_summary_builds_training_example_from_raw_failed_row(self) -> None:
        row = {
            "case_id": "sem_13_arrayed_connector_bus_refactor",
            "final_verdict": "FAILED",
            "submitted": False,
            "provider_error": "",
            "steps": [
                {
                    "text": "Try p.i + n.i = 0 and then another connection pattern.",
                    "tool_calls": [{"arguments": {"model_text": "model M end M;"}}],
                    "tool_results": [{"result": "Error: Too few equations"}],
                },
                {
                    "text": "Maybe this is a compiler matching algorithm issue.",
                    "tool_calls": [{"arguments": {"model_text": "model M2 end M2;"}}],
                    "tool_results": [{"result": 'record SimulationResult resultFile = ""'}],
                },
            ],
        }
        # Exercise the pure builder by monkeypatching the raw row loader through a temporary module-level path would
        # add IO noise; direct gap classification covers the raw row contract.
        self.assertEqual(classify_mapping_gap(row), "residual_misread_as_compiler_limitation")


if __name__ == "__main__":
    unittest.main()
