from __future__ import annotations

import unittest

from gateforge.agent_modelica_semantic_candidate_failure_audit_v0_45_0 import (
    classify_candidate_failure_mode,
    semantic_failure_case_ids,
)


class SemanticCandidateFailureV0450Tests(unittest.TestCase):
    def test_semantic_cases_exclude_submit_signal_cases(self) -> None:
        self.assertEqual(
            semantic_failure_case_ids(
                calibration_summary={"formal_hard_negative_case_ids": ["a", "b"]},
                signal_audit_summary={"cases_with_successful_omc_evidence": ["b"]},
            ),
            ["a"],
        )

    def test_classifies_compiler_limitation_belief(self) -> None:
        row = {"steps": [{"text": "This is a known issue in the matching algorithm.", "tool_results": []}]}
        self.assertEqual(classify_candidate_failure_mode(row), "compiler_limitation_or_matching_algorithm_belief")

    def test_classifies_interface_flow_confusion(self) -> None:
        row = {"steps": [{"text": "The replaceable constrainedby partial contract and flow current ownership are unclear."}]}
        self.assertEqual(classify_candidate_failure_mode(row), "interface_contract_flow_ownership_confusion")


if __name__ == "__main__":
    unittest.main()
