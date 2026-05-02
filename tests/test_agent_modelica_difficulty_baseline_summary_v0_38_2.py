from __future__ import annotations

import unittest

from gateforge.agent_modelica_difficulty_baseline_summary_v0_38_2 import build_difficulty_baseline_summary


class DifficultyBaselineSummaryV0382Tests(unittest.TestCase):
    def test_provider_errors_block_conclusion(self) -> None:
        summary = build_difficulty_baseline_summary(
            [
                {"case_id": "a", "provider": "provider", "final_verdict": "PASS", "provider_error": ""},
                {"case_id": "b", "provider": "provider", "final_verdict": "FAILED", "provider_error": "provider_service_unavailable:503"},
            ]
        )
        self.assertFalse(summary["conclusion_allowed"])
        self.assertEqual(summary["evidence_role"], "smoke")
        self.assertEqual(summary["provider_error_count"], 1)
        self.assertEqual(summary["valid_pass_case_ids"], ["a"])
        self.assertEqual(summary["provider_failed_case_ids"], ["b"])

    def test_clean_run_allows_conclusion(self) -> None:
        summary = build_difficulty_baseline_summary(
            [
                {"case_id": "a", "provider": "provider", "final_verdict": "PASS", "provider_error": ""},
                {"case_id": "b", "provider": "provider", "final_verdict": "FAILED", "provider_error": ""},
            ]
        )
        self.assertTrue(summary["conclusion_allowed"])
        self.assertEqual(summary["evidence_role"], "formal_experiment")
        self.assertEqual(summary["valid_pass_count"], 1)
        self.assertEqual(summary["valid_fail_count"], 1)


if __name__ == "__main__":
    unittest.main()
