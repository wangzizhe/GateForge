from __future__ import annotations

import unittest

from gateforge.agent_modelica_submit_decision_signal_audit_v0_43_2 import (
    build_submit_decision_signal_audit,
    has_empty_resultfile,
    has_successful_omc_evidence,
)


class SubmitDecisionSignalV0432Tests(unittest.TestCase):
    def test_detects_successful_omc_evidence(self) -> None:
        row = {
            "steps": [
                {
                    "tool_results": [
                        {"name": "check_model", "result": 'record SimulationResult\nresultFile = "/workspace/M_res.mat"'}
                    ]
                }
            ]
        }
        self.assertTrue(has_successful_omc_evidence(row))

    def test_detects_empty_resultfile(self) -> None:
        row = {"steps": [{"tool_results": [{"name": "check_model", "result": 'resultFile = ""'}]}]}
        self.assertTrue(has_empty_resultfile(row))

    def test_summary_without_loadable_rows_stays_descriptive(self) -> None:
        summary = build_submit_decision_signal_audit(
            [{"case_id": "case", "result_path": "/missing/results.jsonl", "submitted": False}]
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["decision"], "separate_semantic_failure_from_submit_failure")


if __name__ == "__main__":
    unittest.main()
