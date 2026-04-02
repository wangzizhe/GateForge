from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_12_failure_note import _build_case_note


class AgentModelicaV0312FailureNoteTests(unittest.TestCase):
    def test_build_case_note_marks_early_behavioral_contract_rejection(self) -> None:
        payload = _build_case_note(
            {
                "mutation_id": "demo_case",
                "expected_failure_type": "coupled_conflict_failure",
                "failed_configs": ["baseline", "planner_only"],
                "failure_resolution_paths": ["unresolved"],
                "failure_stage_subtypes": ["stage_3_behavioral_contract_semantic"],
                "planner_invoked_any": True,
                "planner_decisive_any": False,
                "replay_used_any": False,
                "rounds_used_values": [1],
                "elapsed_sec_range": [6.1, 7.0],
            }
        )

        self.assertEqual(payload["terminal_failure_class"], "early_behavioral_contract_rejection")
        self.assertTrue(payload["planner_invoked_any"])
        self.assertFalse(payload["planner_decisive_any"])


if __name__ == "__main__":
    unittest.main()
