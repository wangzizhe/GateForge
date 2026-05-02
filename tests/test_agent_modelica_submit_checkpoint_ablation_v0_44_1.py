from __future__ import annotations

import unittest

from gateforge.agent_modelica_submit_checkpoint_ablation_v0_44_1 import (
    build_submit_checkpoint_ablation_summary,
)


class SubmitCheckpointAblationV0441Tests(unittest.TestCase):
    def test_promotes_when_all_submit_signal_cases_pass(self) -> None:
        summary = build_submit_checkpoint_ablation_summary(
            base_audit={"cases_with_successful_omc_evidence": ["a"]},
            checkpoint_rows=[
                {
                    "case_id": "a",
                    "final_verdict": "PASS",
                    "submitted": True,
                    "provider_error": "",
                    "steps": [{"checkpoint_messages": ["message"]}],
                }
            ],
        )
        self.assertEqual(summary["decision"], "submit_checkpoint_promote_for_submit_signal_slice")
        self.assertEqual(summary["checkpoint_pass_count"], 1)
        self.assertEqual(summary["checkpoint_message_case_ids"], ["a"])

    def test_scope_note_blocks_overgeneralization(self) -> None:
        summary = build_submit_checkpoint_ablation_summary(
            base_audit={"cases_with_successful_omc_evidence": ["a"]},
            checkpoint_rows=[],
        )
        self.assertIn("must not be generalized", summary["scope_note"])


if __name__ == "__main__":
    unittest.main()
