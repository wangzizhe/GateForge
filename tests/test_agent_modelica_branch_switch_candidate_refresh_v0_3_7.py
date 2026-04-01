from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_candidate_refresh_v0_3_7 import (
    refresh_branch_switch_candidates,
)


class BranchSwitchCandidateRefreshTests(unittest.TestCase):
    def test_refresh_merges_results_and_counts_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_refresh_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            results = root / "run_summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "baseline_measurement_protocol": {
                                    "protocol_version": "v0_3_7_branch_switch_baseline_authority_v1"
                                },
                            },
                            {
                                "task_id": "t2",
                                "baseline_measurement_protocol": {
                                    "protocol_version": "v0_3_7_branch_switch_baseline_authority_v1"
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results.write_text(
                json.dumps(
                    {
                        "baseline_measurement_protocol": {
                            "protocol_version": "v0_3_7_branch_switch_baseline_authority_v1"
                        },
                        "results": [
                            {
                                "task_id": "t1",
                                "verdict": "PASS",
                                "executor_status": "PASS",
                                "planner_invoked": True,
                                "resolution_path": "rule_then_llm",
                                "wrong_branch_entered": True,
                                "correct_branch_selected": False,
                            },
                            {
                                "task_id": "t2",
                                "verdict": "PASS",
                                "executor_status": "PASS",
                                "planner_invoked": False,
                                "resolution_path": "deterministic_rule_only",
                                "correct_branch_selected": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_branch_switch_candidates(
                candidate_taskset_path=str(taskset),
                results_path=str(results),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PASS")
        metrics = payload["metrics"]
        self.assertEqual(metrics["total_rows"], 2)
        self.assertEqual(metrics["matched_result_count"], 2)
        self.assertEqual(metrics["planner_invoked_count"], 1)
        self.assertEqual(metrics["deterministic_only_count"], 1)
        self.assertEqual(metrics["wrong_branch_count"], 1)
        self.assertEqual(metrics["correct_branch_count"], 1)


if __name__ == "__main__":
    unittest.main()
