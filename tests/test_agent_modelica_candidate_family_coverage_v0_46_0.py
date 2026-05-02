from __future__ import annotations

import unittest

from gateforge.agent_modelica_candidate_family_coverage_v0_46_0 import (
    build_candidate_family_coverage,
    detect_candidate_families,
)


class CandidateFamilyCoverageV0460Tests(unittest.TestCase):
    def test_detects_candidate_families_from_text(self) -> None:
        row = {"steps": [{"text": "Try p.i + n.i = 0 in ProbeBase and then unroll the for loop."}]}
        families = detect_candidate_families(row)
        self.assertIn("pair_flow_contract", families)
        self.assertIn("base_contract_move", families)
        self.assertIn("loop_unroll", families)

    def test_summary_targets_remaining_semantic_cases(self) -> None:
        summary = build_candidate_family_coverage(
            [
                {
                    "case_id": "sem_06_repl_array_flow",
                    "final_verdict": "FAILED",
                    "submitted": False,
                    "steps": [{"text": "Try a different topology and connection pattern."}],
                },
                {"case_id": "sem_20_arrayed_adapter_cross_node", "steps": [{"text": "irrelevant"}]},
            ]
        )
        self.assertEqual(summary["case_count"], 1)
        self.assertEqual(summary["decision"], "test_uncovered_candidate_families")


if __name__ == "__main__":
    unittest.main()
