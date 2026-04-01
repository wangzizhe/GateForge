from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_same_branch_continuity_candidate_refresh_v0_3_10 import (
    refresh_same_branch_continuity_candidates,
)


class AgentModelicaSameBranchContinuityCandidateRefreshV0310Tests(unittest.TestCase):
    def test_refresh_derives_continuity_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "selected_branch": "continue_on_a",
                                "current_branch": "continue_on_a",
                                "candidate_next_branches": [
                                    {"branch_id": "continue_on_a", "supporting_parameters": ["A"]},
                                    {"branch_id": "switch_to_b", "supporting_parameters": ["B"]},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            detail = root / "t1_result.json"
            detail.write_text(
                json.dumps(
                    {
                        "attempts": [
                            {"round": 1, "check_model_pass": True, "simulate_pass": False, "observed_failure_type": "x", "reason": "y"},
                            {"round": 2, "llm_plan_candidate_parameters": ["A"], "check_model_pass": True, "simulate_pass": False, "observed_failure_type": "x", "reason": "y2"},
                            {"round": 3, "llm_plan_candidate_parameters": ["A"], "check_model_pass": True, "simulate_pass": False, "observed_failure_type": "x2", "reason": "y3"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results = root / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "task_id": "t1",
                                "verdict": "PASS",
                                "executor_status": "PASS",
                                "planner_invoked": True,
                                "resolution_path": "rule_then_llm",
                                "result_json_path": str(detail),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_same_branch_continuity_candidates(
                candidate_taskset_path=str(taskset),
                results_path=str(results),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["metrics"]["success_after_same_branch_continuation_count"], 1)
            self.assertEqual(payload["metrics"]["multi_step_same_branch_success_count_ge_2"], 1)


if __name__ == "__main__":
    unittest.main()
