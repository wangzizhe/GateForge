from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_pure_llm_baseline_report_v0_19_10 as baseline  # noqa: E402


class V01910PureLLMBaselineReportTests(unittest.TestCase):
    def test_classify_splits_single_multi_and_unresolved(self) -> None:
        self.assertEqual(baseline._classify({"executor_status": "PASS", "n_turns": 1}), "llm_solved_single_turn")
        self.assertEqual(baseline._classify({"executor_status": "PASS", "n_turns": 3}), "llm_solved_multi_turn")
        self.assertEqual(baseline._classify({"executor_status": "FAILED", "n_turns": 8}), "unresolved")

    def test_build_report_emits_simplified_counts_and_family_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            benchmark = tmp / "cases.jsonl"
            summary = tmp / "summary.json"
            benchmark.write_text(
                "\n".join(
                    [
                        json.dumps({"candidate_id": "c1", "benchmark_family": "f1", "failure_type": "model_check_error"}),
                        json.dumps({"candidate_id": "c2", "benchmark_family": "f1", "failure_type": "simulate_error"}),
                        json.dumps({"candidate_id": "c3", "benchmark_family": "f2", "failure_type": "constraint_violation"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary.write_text(
                json.dumps(
                    {
                        "summaries": [
                            {"candidate_id": "c1", "executor_status": "PASS", "n_turns": 1, "termination": "success"},
                            {"candidate_id": "c2", "executor_status": "PASS", "n_turns": 3, "termination": "success"},
                            {"candidate_id": "c3", "executor_status": "FAILED", "n_turns": 8, "termination": "max_rounds"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report, records = baseline.build_report(benchmark_path=benchmark, summary_path=summary)

        self.assertEqual(report["classification_counts"]["llm_solved_single_turn"], 1)
        self.assertEqual(report["classification_counts"]["llm_solved_multi_turn"], 1)
        self.assertEqual(report["classification_counts"]["unresolved"], 1)
        self.assertEqual(report["by_family"]["f1"]["llm_solved_single_turn"], 1)
        self.assertEqual(report["by_family"]["f1"]["llm_solved_multi_turn"], 1)
        self.assertEqual(report["by_family"]["f2"]["unresolved"], 1)
        self.assertEqual(len(records), 3)

    def test_contamination_audit_requires_removed_runtime_patterns_to_be_absent(self) -> None:
        audit = baseline._contamination_audit()

        self.assertFalse(audit["contamination_detected"])
        for result in audit["checks"].values():
            self.assertFalse(result["present"])


if __name__ == "__main__":
    unittest.main()
