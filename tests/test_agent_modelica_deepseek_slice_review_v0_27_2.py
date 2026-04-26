from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_deepseek_slice_review_v0_27_2 import (
    build_slice_review_summary,
    classify_omc_feedback,
    run_deepseek_slice_review,
)


def _attempt(round_index: int, raw: str, check_pass: bool) -> dict:
    return {
        "round": round_index,
        "llm_called": True,
        "llm_error": "",
        "patched_text_present": True,
        "model_changed": True,
        "check_pass_after_patch": check_pass,
        "raw_omc_after_patch": raw,
    }


class DeepSeekSliceReviewV0272Tests(unittest.TestCase):
    def test_classify_omc_feedback(self) -> None:
        self.assertEqual(classify_omc_feedback("", check_pass=True), "none")
        self.assertEqual(
            classify_omc_feedback("Error: Wrong number of subscripts in R1Resistance[1]", check_pass=False),
            "wrong_number_of_subscripts",
        )
        self.assertEqual(
            classify_omc_feedback("Error: Too few equations, under-determined system.", check_pass=False),
            "underdetermined_system",
        )

    def test_build_summary_detects_repeated_terminal_failure_and_true_multi_turn(self) -> None:
        rows = [
            {
                "case_id": "fail_a",
                "final_verdict": "FAILED",
                "repair_round_count": 2,
                "executor_attempt_count": 2,
                "observation_validation_error_count": 0,
                "attempts": [
                    _attempt(1, "Error: Wrong number of subscripts", False),
                    _attempt(2, "Error: Too few equations, under-determined system.", False),
                ],
            },
            {
                "case_id": "pass_b",
                "final_verdict": "PASS",
                "repair_round_count": 2,
                "executor_attempt_count": 2,
                "observation_validation_error_count": 0,
                "attempts": [
                    _attempt(1, "Error: Wrong number of subscripts", False),
                    _attempt(2, "Check completed successfully", True),
                ],
            },
            {
                "case_id": "fail_c",
                "final_verdict": "FAILED",
                "repair_round_count": 2,
                "executor_attempt_count": 2,
                "observation_validation_error_count": 0,
                "attempts": [
                    _attempt(1, "Error: Wrong number of subscripts", False),
                    _attempt(2, "Error: Too few equations, under-determined system.", False),
                ],
            },
        ]
        case_reviews, summary = build_slice_review_summary(rows)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["true_multi_turn_count"], 1)
        self.assertEqual(summary["repeated_failure_signature"], "underdetermined_system")
        self.assertEqual(summary["decision"], "hold_family_expansion_review_residuals")
        self.assertTrue(case_reviews[1]["true_multi_turn"])

    def test_run_review_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_results = root / "results.jsonl"
            input_results.write_text(
                json.dumps(
                    {
                        "case_id": "c1",
                        "final_verdict": "PASS",
                        "repair_round_count": 1,
                        "executor_attempt_count": 1,
                        "observation_validation_error_count": 0,
                        "attempts": [_attempt(1, "Check completed successfully", True)],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = run_deepseek_slice_review(input_results=input_results, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "case_reviews.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
