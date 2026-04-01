from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_failure_classifier_v0_3_7 import (
    build_branch_switch_failure_classifier,
    classify_branch_switch_row,
)


class BranchSwitchFailureClassifierTests(unittest.TestCase):
    def test_classify_success_after_branch_switch(self) -> None:
        row = {
            "executor_status": "PASS",
            "resolution_path": "rule_then_llm",
            "correct_branch_selected": True,
        }
        self.assertEqual(classify_branch_switch_row(row)["failure_bucket"], "success_after_branch_switch")

    def test_classify_wrong_branch_after_restore(self) -> None:
        row = {
            "executor_status": "FAILED",
            "planner_invoked": True,
            "wrong_branch_entered": True,
            "correct_branch_selected": False,
        }
        self.assertEqual(classify_branch_switch_row(row)["failure_bucket"], "wrong_branch_after_restore")

    def test_build_classifier_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_branch_switch_classifier_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "a",
                                "executor_status": "PASS",
                                "resolution_path": "rule_then_llm",
                                "correct_branch_selected": True,
                            },
                            {
                                "task_id": "b",
                                "executor_status": "FAILED",
                                "planner_invoked": True,
                                "wrong_branch_entered": True,
                                "correct_branch_selected": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_branch_switch_failure_classifier(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
        counts = payload["metrics"]["failure_bucket_counts"]
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["metrics"]["total_rows"], 2)
        self.assertEqual(counts["success_after_branch_switch"], 1)
        self.assertEqual(counts["wrong_branch_after_restore"], 1)


if __name__ == "__main__":
    unittest.main()
