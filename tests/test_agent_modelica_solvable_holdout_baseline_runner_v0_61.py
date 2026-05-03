from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_solvable_holdout_baseline_runner_v0_61_2 import (
    load_holdout_tasks,
    run_solvable_holdout_baseline,
    run_solvable_holdout_baseline_streaming,
)


class SolvableHoldoutBaselineRunnerV061Tests(unittest.TestCase):
    def test_load_holdout_tasks_filters_dev_and_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tasks.jsonl"
            path.write_text(
                '{"case_id":"dev_a","dataset_split":"dev"}\n'
                '{"case_id":"holdout_a","dataset_split":"holdout"}\n'
                '{"case_id":"frontier_a","dataset_split":"frontier"}\n',
                encoding="utf-8",
            )
            self.assertEqual([task["case_id"] for task in load_holdout_tasks(path)], ["holdout_a"])

    def test_runner_writes_summary_and_results_with_mock_run_case(self) -> None:
        def mock_run_case(case: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {
                "case_id": case["case_id"],
                "final_verdict": "PASS",
                "final_model_text": case["model_text"],
                "provider_error": "",
                "submitted": True,
                "steps": [],
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(
                '{"case_id":"case_a","dataset_split":"holdout","task_type":"repair","description":"Repair.",'
                '"constraints":[],"initial_model":"model Demo end Demo;","verification":{"check_model":true,"simulate":{}}}\n',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_solvable_holdout_baseline(tasks_path=tasks, out_dir=out, run_case_fn=mock_run_case)
            self.assertEqual(summary["case_count"], 1)
            self.assertEqual(summary["pass_count"], 1)
            self.assertTrue((out / "results.jsonl").exists())

    def test_streaming_runner_writes_after_each_case(self) -> None:
        def mock_run_case(case: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            return {
                "case_id": case["case_id"],
                "final_verdict": "FAILED",
                "final_model_text": case["model_text"],
                "provider_error": "",
                "submitted": False,
                "steps": [],
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(
                '{"case_id":"case_a","dataset_split":"holdout","task_type":"repair","description":"Repair.",'
                '"constraints":[],"initial_model":"model Demo end Demo;","verification":{"check_model":true,"simulate":{}}}\n',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_solvable_holdout_baseline_streaming(tasks_path=tasks, out_dir=out, run_case_fn=mock_run_case)
            self.assertEqual(summary["completed_case_count"], 1)
            self.assertEqual(summary["fail_count"], 1)
            self.assertEqual(len((out / "results.jsonl").read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
