from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_external_bundle_v0_57_0 import (
    build_benchmark_external_bundle,
    build_external_task,
    run_benchmark_external_bundle,
)


class BenchmarkExternalBundleV057Tests(unittest.TestCase):
    def test_external_task_omits_hidden_fields(self) -> None:
        task = build_external_task(
            {
                "case_id": "case_a",
                "title": "Task",
                "description": "Repair.",
                "initial_model": "model Demo end Demo;",
                "hidden_oracle": {"answer": "x"},
                "reference_repair": "hidden",
            },
            split="holdout",
        )
        self.assertNotIn("hidden_oracle", task)
        self.assertNotIn("reference_repair", task)
        self.assertEqual(task["dataset_split"], "holdout")

    def test_bundle_reports_missing_task_records(self) -> None:
        summary, tasks = build_benchmark_external_bundle(
            split_summary={"split_case_ids": {"dev": ["case_a"], "holdout": ["missing"]}},
            tasks_by_case={"case_a": {"case_id": "case_a", "title": "Task", "description": "Repair.", "initial_model": "model Demo end Demo;"}},
        )
        self.assertEqual(len(tasks), 1)
        self.assertEqual(summary["missing_task_case_ids"], ["missing"])
        self.assertIn("missing_task_records", summary["gaps"])

    def test_run_external_bundle_writes_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split = root / "split.json"
            split.write_text('{"split_case_ids":{"dev":["case_a"],"holdout":[]}}', encoding="utf-8")
            task_dir = root / "tasks"
            task_dir.mkdir()
            (task_dir / "case_a.json").write_text(
                '{"case_id":"case_a","title":"Task","description":"Repair.",'
                '"initial_model":"model Demo end Demo;","verification":{"check_model":true}}',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_benchmark_external_bundle(split_path=split, task_dirs=(task_dir,), task_jsonl_paths=(), out_dir=out)
            self.assertEqual(summary["task_count"], 1)
            self.assertTrue((out / "tasks.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
