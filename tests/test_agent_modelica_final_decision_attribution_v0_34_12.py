from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_final_decision_attribution_v0_34_12 import (
    build_final_decision_attribution,
)


def _write_run(
    root: Path,
    *,
    verdict: str,
    submitted: bool,
    include_oracle: bool,
    continue_after_oracle: bool = False,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    steps = [
        {
            "step": 1,
            "text": "Candidate compiles and simulates.",
            "tool_calls": [{"name": "simulate_model"}],
            "tool_results": [{"name": "simulate_model", "result": 'resultFile = "/workspace/X.mat"'}],
        },
    ]
    if include_oracle:
        steps.append(
            {
                "step": 2,
                "text": "Check reusable contract.",
                "tool_calls": [{"name": "reusable_contract_oracle_diagnostic"}],
                "tool_results": [
                    {"name": "reusable_contract_oracle_diagnostic", "result": '{"contract_oracle_pass": true}'}
                ],
            }
        )
    if continue_after_oracle:
        steps.append(
            {
                "step": 3,
                "text": "Try a cleaner candidate instead of submitting.",
                "tool_calls": [{"name": "check_model"}],
                "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/Y.mat"'}],
            }
        )
    if submitted:
        steps.append(
            {
                "step": 4,
                "text": "Submit.",
                "tool_calls": [{"name": "submit_final"}],
                "tool_results": [{"name": "submit_final", "result": '{"status": "submitted"}'}],
            }
        )
    row = {
        "case_id": "case_a",
        "final_verdict": verdict,
        "submitted": submitted,
        "provider_error": "",
        "token_used": 10,
        "step_count": len(steps),
        "steps": steps,
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class FinalDecisionAttributionV03412Tests(unittest.TestCase):
    def test_classifies_oracle_pass_then_continued_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "a"
            _write_run(
                run_a,
                verdict="FAILED",
                submitted=False,
                include_oracle=True,
                continue_after_oracle=True,
            )
            summary = build_final_decision_attribution(run_dirs=[run_a], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["oracle_pass_without_submit_count"], 1)
            self.assertEqual(
                summary["failure_class_counts"]["oracle_pass_then_continued_candidate_search_until_limit"],
                1,
            )
            self.assertEqual(summary["decision"], "final_decision_instability_after_oracle_pass")

    def test_classifies_submitted_after_oracle_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "a"
            _write_run(run_a, verdict="PASS", submitted=True, include_oracle=True)
            summary = build_final_decision_attribution(run_dirs=[run_a], out_dir=root / "out")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["failure_class_counts"]["submitted_after_success_and_oracle_pass"], 1)

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_final_decision_attribution(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
