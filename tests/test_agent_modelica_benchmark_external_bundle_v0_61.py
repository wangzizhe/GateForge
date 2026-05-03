from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_external_bundle_v0_61_0 import (
    build_freeze_ready_external_bundle,
    run_freeze_ready_external_bundle,
)


class BenchmarkExternalBundleV061Tests(unittest.TestCase):
    def test_freeze_ready_bundle_excludes_frontier_and_near_miss(self) -> None:
        summary, tasks = build_freeze_ready_external_bundle(
            split_summary={
                "split_case_ids": {
                    "dev": ["dev_a"],
                    "holdout": ["holdout_a"],
                    "frontier": ["frontier_a"],
                    "near_miss_reference_queue": ["near_a"],
                }
            },
            tasks_by_case={
                "dev_a": {"case_id": "dev_a", "title": "Dev", "description": "Repair.", "initial_model": "model A end A;"},
                "holdout_a": {"case_id": "holdout_a", "title": "Holdout", "description": "Repair.", "initial_model": "model B end B;"},
                "frontier_a": {"case_id": "frontier_a", "title": "Frontier", "description": "Repair.", "initial_model": "model C end C;"},
            },
        )
        self.assertEqual(summary["task_count"], 2)
        self.assertTrue(summary["frontier_excluded_from_bundle"])
        self.assertEqual([task["case_id"] for task in tasks], ["dev_a", "holdout_a"])

    def test_run_freeze_ready_bundle_writes_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split = root / "split.json"
            split.write_text('{"split_case_ids":{"dev":["case_a"],"holdout":[],"frontier":["frontier_a"]}}', encoding="utf-8")
            task_dir = root / "tasks"
            task_dir.mkdir()
            (task_dir / "case_a.json").write_text(
                '{"case_id":"case_a","title":"Task","description":"Repair.","initial_model":"model Demo end Demo;"}',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_freeze_ready_external_bundle(split_path=split, task_dirs=(task_dir,), task_jsonl_paths=(), out_dir=out)
            self.assertEqual(summary["task_count"], 1)
            self.assertTrue((out / "tasks.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
