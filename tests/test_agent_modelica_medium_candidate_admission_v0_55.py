from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_medium_candidate_admission_v0_55_0 import (
    audit_visible_blindness,
    build_medium_candidate_admission,
    load_task_records,
    run_medium_candidate_admission,
)


class MediumCandidateAdmissionV055Tests(unittest.TestCase):
    def test_visible_blindness_blocks_direct_answer_leakage(self) -> None:
        issues = audit_visible_blindness({"description": "The root cause is missing p.i = 0. Add this equation."})
        self.assertIn("forbidden_visible_phrase:root cause is", issues)
        self.assertIn("forbidden_visible_phrase:add this equation", issues)

    def test_build_admission_accepts_source_backed_medium_candidate(self) -> None:
        summary = build_medium_candidate_admission(
            candidates=[{"case_id": "case_a", "pass_rate": 0.5, "evidence_count": 2}],
            tasks_by_case={
                "case_a": {
                    "case_id": "case_a",
                    "task_type": "repair",
                    "source_backed": True,
                    "initial_model": "model Demo end Demo;",
                    "verification": {"check_model": True, "simulate": {"stop_time": 0.1}},
                    "_source_path": "task.json",
                }
            },
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["admitted_case_ids"], ["case_a"])

    def test_load_task_records_reads_json_and_jsonl_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "tasks"
            task_dir.mkdir()
            (task_dir / "case_a.json").write_text('{"case_id":"case_a"}', encoding="utf-8")
            task_jsonl = root / "tasks.jsonl"
            task_jsonl.write_text('{"case_id":"case_b"}\n', encoding="utf-8")
            tasks = load_task_records(task_dirs=(task_dir,), task_jsonl_paths=(task_jsonl,))
        self.assertIn("case_a", tasks)
        self.assertIn("case_b", tasks)

    def test_run_admission_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            candidates.write_text('{"case_id":"case_a","pass_rate":0.5,"evidence_count":2}\n', encoding="utf-8")
            task_dir = root / "tasks"
            task_dir.mkdir()
            (task_dir / "case_a.json").write_text(
                '{"case_id":"case_a","task_type":"repair","source_backed":true,'
                '"initial_model":"model Demo end Demo;","verification":{"check_model":true,"simulate":{}}}',
                encoding="utf-8",
            )
            out = root / "out"
            summary = run_medium_candidate_admission(candidates_path=candidates, task_dirs=(task_dir,), task_jsonl_paths=(), out_dir=out)
            self.assertEqual(summary["admitted_count"], 1)
            self.assertTrue((out / "admitted_medium_case_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
