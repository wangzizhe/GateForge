from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_12_candidate_refresh import (
    refresh_v0_3_12_candidates,
)


class AgentModelicaV0312CandidateRefreshTests(unittest.TestCase):
    def test_refresh_derives_branch_sequence_and_hygiene_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result_json = root / "detail.json"
            result_json.write_text(
                json.dumps(
                    {
                        "executor_status": "PASS",
                        "executor_runtime_hygiene": {
                            "planner_event_count": 1,
                            "rollback_applied_count": 1,
                        },
                        "attempts": [
                            {"round": 1, "llm_plan_candidate_parameters": ["a"]},
                            {"round": 2, "llm_plan_candidate_parameters": ["a"]},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "demo",
                                "candidate_branches": [
                                    {"branch_id": "continue_on_a", "supporting_parameters": ["a"]},
                                    {"branch_id": "switch_to_b", "supporting_parameters": ["b"]},
                                ],
                            }
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
                                "task_id": "demo",
                                "verdict": "PASS",
                                "result_json_path": str(result_json),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_v0_3_12_candidates(
                candidate_taskset_path=str(taskset),
                results_path=str(results),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["metrics"]["planner_event_case_count"], 1)
            self.assertEqual(payload["metrics"]["rollback_applied_case_count"], 1)
            self.assertEqual(payload["tasks"][0]["detected_branch_sequence"], ["continue_on_a"])

    def test_unmatched_rows_do_not_reuse_stale_task_result_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stale_result = root / "stale.json"
            stale_result.write_text(
                json.dumps(
                    {
                        "executor_status": "PASS",
                        "executor_runtime_hygiene": {"planner_event_count": 1},
                    }
                ),
                encoding="utf-8",
            )
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "demo",
                                "verdict": "PASS",
                                "result_json_path": str(stale_result),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results = root / "results.json"
            results.write_text(json.dumps({"results": []}), encoding="utf-8")

            payload = refresh_v0_3_12_candidates(
                candidate_taskset_path=str(taskset),
                results_path=str(results),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["metrics"]["matched_result_count"], 0)
            self.assertEqual(payload["metrics"]["successful_case_count"], 0)
            self.assertEqual(payload["tasks"][0]["verdict"], "")
            self.assertEqual(payload["tasks"][0]["result_json_path"], "")


if __name__ == "__main__":
    unittest.main()
