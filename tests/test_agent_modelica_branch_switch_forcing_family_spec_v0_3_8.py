from __future__ import annotations

import unittest

from gateforge.agent_modelica_branch_switch_forcing_family_spec_v0_3_8 import (
    FAMILY_ID,
    build_lane_summary,
    run_candidate_ready_gates,
)


def _candidate() -> dict:
    return {
        "task_id": "t1",
        "v0_3_8_family_id": FAMILY_ID,
        "required_entry_bucket": "stalled_search_after_progress",
        "current_branch": "continue_on_r",
        "preferred_branch": "switch_to_c",
        "candidate_branches": [
            {
                "branch_id": "continue_on_r",
                "branch_kind": "continue_current_line",
                "trigger_signal": "stalled_search_after_progress",
            },
            {
                "branch_id": "switch_to_c",
                "branch_kind": "branch_switch_candidate",
                "trigger_signal": "stalled_search_after_progress",
            },
        ],
        "branch_forcing_design": {
            "required_entry_state": "stalled_search_after_progress",
            "wrong_branch_outcome": "wrong_branch_after_restore",
            "success_mode_target": "success_after_branch_switch",
            "branch_order": ["continue_on_r", "switch_to_c"],
        },
        "baseline_measurement_protocol": {
            "protocol_version": "v0_3_8_branch_switch_forcing_baseline_authority_v1",
            "baseline_lever_name": "simulate_error_parameter_recovery_sweep",
            "baseline_reference_version": "v0.3.7",
            "enabled_policy_flags": {
                "allow_baseline_single_sweep": True,
                "allow_branch_switch_replan_policy": False,
            },
        },
    }


class BranchSwitchForcingFamilySpecV038Tests(unittest.TestCase):
    def test_candidate_ready_gates_pass_on_valid_candidate(self) -> None:
        payload = run_candidate_ready_gates(_candidate())
        self.assertTrue(payload["passed"])

    def test_lane_summary_needs_minimum_case_count(self) -> None:
        payload = build_lane_summary([_candidate() for _ in range(7)])
        self.assertEqual(payload["lane_status"], "NEEDS_MORE_GENERATION")


if __name__ == "__main__":
    unittest.main()
