from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_12_one_shot_family_spec import (
    build_lane_summary_from_taskset,
)


class AgentModelicaV0312OneShotFamilySpecTests(unittest.TestCase):
    def test_marks_lane_candidate_ready_at_eight_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            rows = []
            for idx in range(8):
                rows.append(
                    {
                        "task_id": f"case_{idx}",
                        "v0_3_12_family_id": "same_branch_one_shot_after_partial_progress",
                        "source_primary_bucket": "single_branch_resolution_without_true_stall",
                        "current_branch": "continue_on_a",
                        "selected_branch": "continue_on_a",
                        "preferred_branch": "switch_to_b",
                        "candidate_branches": [
                            {"branch_id": "continue_on_a"},
                            {"branch_id": "switch_to_b"},
                        ],
                        "baseline_measurement_protocol": {
                            "protocol_version": "v0_3_12_one_shot_baseline_authority_v1",
                            "baseline_lever_name": "same_branch_one_shot_or_accidental_success",
                            "baseline_reference_version": "v0.3.10",
                            "enabled_policy_flags": {
                                "allow_branch_switch_replan_policy": False,
                                "allow_same_branch_continuity_policy": False,
                            },
                        },
                    }
                )
            taskset.write_text(json.dumps({"tasks": rows}), encoding="utf-8")
            payload = build_lane_summary_from_taskset(
                candidate_taskset_path=str(taskset),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["lane_status"], "CANDIDATE_READY")
            self.assertEqual(payload["admitted_count"], 8)


if __name__ == "__main__":
    unittest.main()
