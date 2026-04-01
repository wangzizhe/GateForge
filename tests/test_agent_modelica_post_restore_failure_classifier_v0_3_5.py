from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_post_restore_failure_classifier_v0_3_5 import (
    build_post_restore_failure_classifier,
    classify_post_restore_row,
)


class AgentModelicaPostRestoreFailureClassifierV035Tests(unittest.TestCase):
    def test_classify_success_after_restore(self) -> None:
        row = {
            "executor_status": "PASS",
            "resolution_path": "rule_then_llm",
            "attempts": [
                {"simulate_error_parameter_recovery": {"applied": True}},
            ],
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification.get("failure_bucket"), "success_after_restore")

    def test_classify_residual_semantic_conflict(self) -> None:
        row = {
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "attempts": [
                {"simulate_error_parameter_recovery": {"applied": True}},
            ],
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification.get("failure_bucket"), "residual_semantic_conflict_after_restore")

    def test_classify_verifier_reject_after_restore(self) -> None:
        row = {
            "executor_status": "FAILED",
            "check_model_pass": True,
            "simulate_pass": False,
            "attempts": [
                {"simulate_error_parameter_recovery": {"applied": True}},
            ],
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification.get("failure_bucket"), "verifier_reject_after_restore")

    def test_classify_wrong_branch_after_restore(self) -> None:
        row = {
            "executor_status": "FAILED",
            "wrong_branch_entered": True,
            "correct_branch_selected": False,
            "attempts": [
                {"source_repair": {"applied": True}},
            ],
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification.get("failure_bucket"), "wrong_branch_after_restore")

    def test_classify_no_meaningful_progress(self) -> None:
        row = {
            "executor_status": "FAILED",
            "check_model_pass": False,
            "simulate_pass": False,
            "attempts": [],
        }
        classification = classify_post_restore_row(row)
        self.assertEqual(classification.get("failure_bucket"), "no_meaningful_progress")

    def test_build_classifier_counts_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v035_post_restore_classifier_") as td:
            root = Path(td)
            payload = {
                "results": [
                    {
                        "task_id": "case_a",
                        "executor_status": "PASS",
                        "resolution_path": "rule_then_llm",
                        "attempts": [{"simulate_error_parameter_recovery": {"applied": True}}],
                    },
                    {
                        "task_id": "case_b",
                        "executor_status": "FAILED",
                        "check_model_pass": True,
                        "simulate_pass": False,
                        "attempts": [{"simulate_error_parameter_recovery": {"applied": True}}],
                    },
                ]
            }
            input_path = root / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            summary = build_post_restore_failure_classifier(
                input_path=str(input_path),
                out_dir=str(root / "out"),
            )
        counts = ((summary.get("metrics") or {}).get("failure_bucket_counts") or {})
        self.assertEqual(counts.get("success_after_restore"), 1)
        self.assertEqual(counts.get("verifier_reject_after_restore"), 1)

    def test_build_classifier_accepts_directory_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v035_post_restore_classifier_dir_") as td:
            root = Path(td)
            input_dir = root / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "case_a.json").write_text(
                json.dumps(
                    {
                        "task_id": "case_a",
                        "executor_status": "PASS",
                        "resolution_path": "rule_then_llm",
                        "attempts": [{"simulate_error_parameter_recovery": {"applied": True}}],
                    }
                ),
                encoding="utf-8",
            )
            summary = build_post_restore_failure_classifier(
                input_path=str(input_dir),
                out_dir=str(root / "out"),
            )
        self.assertEqual((summary.get("metrics") or {}).get("total_rows"), 1)


if __name__ == "__main__":
    unittest.main()
