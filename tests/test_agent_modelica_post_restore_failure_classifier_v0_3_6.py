from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_post_restore_failure_classifier_v0_3_6 import (
    build_post_restore_failure_classifier,
    classify_post_restore_row,
)


class AgentModelicaPostRestoreFailureClassifierV036Tests(unittest.TestCase):
    def test_classify_success_beyond_single_sweep(self) -> None:
        row = {
            "executor_status": "PASS",
            "resolution_path": "rule_then_llm",
            "single_sweep_outcome": "residual_failure_after_first_correction",
            "first_correction_success": True,
            "residual_failure_after_first_correction": True,
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification["failure_bucket"], "success_beyond_single_sweep")

    def test_classify_success_with_single_sweep_only(self) -> None:
        row = {
            "executor_status": "PASS",
            "resolution_path": "rule_then_llm",
            "single_sweep_outcome": "resolved",
            "first_correction_success": True,
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification["failure_bucket"], "success_with_single_sweep_only")

    def test_classify_wrong_branch_after_restore(self) -> None:
        row = {
            "executor_status": "FAILED",
            "planner_invoked": True,
            "wrong_branch_entered": True,
            "correct_branch_selected": False,
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification["failure_bucket"], "wrong_branch_after_restore")

    def test_classify_verifier_reject_after_restore(self) -> None:
        row = {
            "executor_status": "FAILED",
            "first_correction_success": True,
            "check_model_pass": True,
            "simulate_pass": False,
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification["failure_bucket"], "verifier_reject_after_restore")

    def test_build_classifier_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_post_restore_classifier_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "case_a",
                                "executor_status": "PASS",
                                "resolution_path": "rule_then_llm",
                                "single_sweep_outcome": "residual_failure_after_first_correction",
                                "first_correction_success": True,
                                "residual_failure_after_first_correction": True,
                            },
                            {
                                "task_id": "case_b",
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
            payload = build_post_restore_failure_classifier(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
        metrics = payload["metrics"]
        counts = metrics["failure_bucket_counts"]
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(metrics["total_rows"], 2)
        self.assertEqual(counts["success_beyond_single_sweep"], 1)
        self.assertEqual(counts["wrong_branch_after_restore"], 1)


if __name__ == "__main__":
    unittest.main()
