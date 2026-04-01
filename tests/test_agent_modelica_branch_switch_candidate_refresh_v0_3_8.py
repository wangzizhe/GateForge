from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_candidate_refresh_v0_3_8 import (
    refresh_branch_switch_candidates,
)


class BranchSwitchCandidateRefreshV038Tests(unittest.TestCase):
    def test_refresh_derives_branch_switch_evidence_from_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            detail_path = root / "detail.json"
            detail_path.write_text(
                json.dumps(
                    {
                        "attempts": [
                            {"round": 1},
                            {
                                "round": 2,
                                "llm_plan_candidate_parameters": ["R", "C"],
                            },
                            {
                                "round": 3,
                                "llm_plan_candidate_parameters": ["C"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset_path = root / "taskset.json"
            taskset_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "demo",
                                "candidate_branches": [
                                    {
                                        "branch_id": "continue_on_R",
                                        "supporting_parameters": ["R"],
                                    },
                                    {
                                        "branch_id": "switch_to_C",
                                        "supporting_parameters": ["C"],
                                    },
                                ],
                                "current_branch": "continue_on_R",
                                "preferred_branch": "switch_to_C",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results_path = root / "results.json"
            results_path.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "task_id": "demo",
                                "verdict": "PASS",
                                "executor_status": "PASS",
                                "planner_invoked": True,
                                "rounds_used": 4,
                                "resolution_path": "rule_then_llm",
                                "result_json_path": str(detail_path),
                                "candidate_branches": [
                                    {
                                        "branch_id": "continue_on_R",
                                        "supporting_parameters": ["R"],
                                    },
                                    {
                                        "branch_id": "switch_to_C",
                                        "supporting_parameters": ["C"],
                                    },
                                ],
                                "current_branch": "continue_on_R",
                                "preferred_branch": "switch_to_C",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_branch_switch_candidates(
                candidate_taskset_path=str(taskset_path),
                results_path=str(results_path),
                out_dir=str(root / "out"),
            )
            row = payload["tasks"][0]
            self.assertTrue(row["stall_event_observed"])
            self.assertTrue(row["branch_switch_event_observed"])
            self.assertTrue(row["wrong_branch_entered"])
            self.assertTrue(row["correct_branch_selected"])
            self.assertTrue(row["branch_switch_contributed_to_success"])
            self.assertTrue(row["success_after_branch_switch"])


if __name__ == "__main__":
    unittest.main()
