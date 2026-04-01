from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_family_spec_v0_3_7 import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    FAMILY_ID,
    build_lane_summary,
    build_lane_summary_from_taskset,
    check_branch_candidates_gate,
    check_entry_state_gate,
    check_family_gate,
    check_measurement_protocol_gate,
)


def _candidate(task_id: str = "t1") -> dict:
    return {
        "task_id": task_id,
        "v0_3_7_family_id": FAMILY_ID,
        "required_entry_bucket": "stalled_search_after_progress",
        "current_branch": "continue_on_R",
        "preferred_branch": "switch_to_C",
        "candidate_branches": [
            {
                "branch_id": "continue_on_R",
                "branch_kind": "continue_current_line",
                "trigger_signal": "stalled_search_after_progress",
                "viability_status": "plausible_but_stalled",
                "supporting_parameters": ["R"],
            },
            {
                "branch_id": "switch_to_C",
                "branch_kind": "branch_switch_candidate",
                "trigger_signal": "stalled_search_after_progress",
                "viability_status": "preferred_after_stall",
                "supporting_parameters": ["C"],
            },
        ],
        "baseline_measurement_protocol": {
            "protocol_version": BASELINE_PROTOCOL_VERSION,
            "baseline_lever_name": BASELINE_LEVER_NAME,
            "baseline_reference_version": BASELINE_REFERENCE_VERSION,
            "enabled_policy_flags": {
                "allow_baseline_single_sweep": True,
                "allow_branch_switch_replan_policy": False,
            },
        },
    }


class BranchSwitchFamilySpecTests(unittest.TestCase):
    def test_family_gate_passes(self) -> None:
        passed, reason = check_family_gate(_candidate())
        self.assertTrue(passed)
        self.assertIn("family_ok", reason)

    def test_entry_state_gate_requires_stall(self) -> None:
        passed, reason = check_entry_state_gate({**_candidate(), "required_entry_bucket": "wrong_branch_after_restore"})
        self.assertFalse(passed)
        self.assertIn("required_entry_bucket_not_supported", reason)

    def test_branch_candidates_gate_requires_structured_candidates(self) -> None:
        bad = _candidate()
        bad["candidate_branches"] = [{"branch_id": "continue_on_R"}]
        passed, reason = check_branch_candidates_gate(bad)
        self.assertFalse(passed)
        self.assertIn("too_small", reason)

    def test_branch_candidates_gate_rejects_same_preferred_and_current(self) -> None:
        bad = _candidate()
        bad["preferred_branch"] = "continue_on_R"
        passed, reason = check_branch_candidates_gate(bad)
        self.assertFalse(passed)
        self.assertEqual(reason, "preferred_branch_must_differ_from_current_branch")

    def test_measurement_protocol_gate_checks_baseline_flags(self) -> None:
        bad = _candidate()
        bad["baseline_measurement_protocol"]["enabled_policy_flags"]["allow_branch_switch_replan_policy"] = True
        passed, reason = check_measurement_protocol_gate(bad)
        self.assertFalse(passed)
        self.assertEqual(reason, "branch_switch_policy_must_be_disabled_in_baseline")

    def test_build_lane_summary_candidate_ready(self) -> None:
        payload = build_lane_summary([_candidate(f"t{i}") for i in range(8)])
        self.assertEqual(payload["lane_status"], "CANDIDATE_READY")
        self.assertEqual(payload["admitted_count"], 8)

    def test_build_lane_summary_from_taskset_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_family_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [_candidate("a"), _candidate("b")]}), encoding="utf-8")
            payload = build_lane_summary_from_taskset(candidate_taskset_path=str(taskset), out_dir=str(root / "out"))
        self.assertEqual(payload["lane_status"], "NEEDS_MORE_GENERATION")
        self.assertEqual(payload["total_candidate_count"], 2)


if __name__ == "__main__":
    unittest.main()
