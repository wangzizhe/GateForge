from __future__ import annotations

import unittest

from gateforge.agent_modelica_same_branch_continuity_family_spec_v0_3_10 import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    FAMILY_ID,
    SOURCE_BUCKET,
    build_lane_summary,
)


def _candidate(task_id: str = "t1") -> dict:
    return {
        "task_id": task_id,
        "v0_3_10_family_id": FAMILY_ID,
        "source_primary_bucket": SOURCE_BUCKET,
        "current_branch": "continue_on_m",
        "selected_branch": "continue_on_m",
        "detected_branch_sequence": ["continue_on_m"],
        "success_without_branch_switch_evidence": True,
        "success_after_branch_switch": False,
        "branch_switch_event_observed": False,
        "baseline_measurement_protocol": {
            "protocol_version": BASELINE_PROTOCOL_VERSION,
            "baseline_lever_name": BASELINE_LEVER_NAME,
            "baseline_reference_version": BASELINE_REFERENCE_VERSION,
            "enabled_policy_flags": {
                "allow_branch_switch_replan_policy": False,
                "allow_same_branch_continuity_policy": False,
            },
        },
    }


class AgentModelicaSameBranchContinuityFamilySpecV0310Tests(unittest.TestCase):
    def test_candidate_ready_requires_minimum_size(self) -> None:
        summary = build_lane_summary([_candidate(f"t{i}") for i in range(4)])
        self.assertEqual(summary["lane_status"], "NEEDS_MORE_GENERATION")
        self.assertEqual(summary["admitted_count"], 4)

    def test_rejects_multi_branch_sequence(self) -> None:
        row = _candidate()
        row["detected_branch_sequence"] = ["continue_on_m", "switch_to_d"]
        summary = build_lane_summary([row])
        self.assertEqual(summary["admitted_count"], 0)
        self.assertIn("branch_identity_gate:branch_sequence_not_single_branch", summary["rejection_summary"])


if __name__ == "__main__":
    unittest.main()
