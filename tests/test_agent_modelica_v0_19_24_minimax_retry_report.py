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

from build_minimax_final_report_v0_19_24 import build_final_report  # noqa: E402
from build_minimax_retry_subset_v0_19_24 import build_retry_subset  # noqa: E402


class V01924MiniMaxRetryReportTests(unittest.TestCase):
    def test_build_retry_subset_selects_only_failed_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            benchmark_path = root / "benchmark.jsonl"
            baseline_summary_path = root / "summary.json"
            benchmark_rows = [
                {"candidate_id": "a"},
                {"candidate_id": "b"},
                {"candidate_id": "c"},
            ]
            benchmark_path.write_text(
                "\n".join(json.dumps(row) for row in benchmark_rows) + "\n",
                encoding="utf-8",
            )
            baseline_summary_path.write_text(
                json.dumps(
                    {
                        "summaries": [
                            {"candidate_id": "a", "executor_status": "PASS"},
                            {"candidate_id": "b", "executor_status": "FAILED"},
                            {"candidate_id": "c", "executor_status": "FAILED"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            subset = build_retry_subset(benchmark_path, baseline_summary_path)

        self.assertEqual([row["candidate_id"] for row in subset], ["b", "c"])

    def test_build_final_report_merges_retry_results(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first_pass_path = root / "first.json"
            retry_path = root / "retry.json"
            first_pass_path.write_text(
                json.dumps(
                    {
                        "aggregate": {"pass_rate": 0.5},
                        "summaries": [
                            {"candidate_id": "a", "benchmark_family": "fam", "executor_status": "PASS", "n_turns": 2, "turn_shape": "single_fix_closure"},
                            {"candidate_id": "b", "benchmark_family": "fam", "executor_status": "FAILED", "n_turns": 1, "turn_shape": "unresolved"},
                            {"candidate_id": "c", "benchmark_family": "fam", "executor_status": "FAILED", "n_turns": 1, "turn_shape": "unresolved"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            retry_path.write_text(
                json.dumps(
                    {
                        "aggregate": {"pass_rate": 0.5},
                        "summaries": [
                            {"candidate_id": "b", "benchmark_family": "fam", "executor_status": "PASS", "n_turns": 2, "turn_shape": "single_fix_closure"},
                            {"candidate_id": "c", "benchmark_family": "fam", "executor_status": "FAILED", "n_turns": 2, "turn_shape": "unresolved"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = build_final_report(first_pass_path, retry_path)

        self.assertEqual(report["recovered_case_count"], 1)
        self.assertEqual(report["still_failed_case_count"], 1)
        self.assertEqual(report["post_retry_aggregate"]["pass_rate"], 0.667)
        self.assertEqual(report["recovered_case_ids"], ["b"])
        self.assertEqual(report["still_failed_case_ids"], ["c"])


if __name__ == "__main__":
    unittest.main()
