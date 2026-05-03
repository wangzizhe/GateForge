from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_split_plan_v0_56_0 import build_benchmark_split_plan, run_benchmark_split_plan


class BenchmarkSplitPlanV056Tests(unittest.TestCase):
    def test_split_plan_separates_dev_and_holdout_without_overlap(self) -> None:
        summary = build_benchmark_split_plan(
            relayer_summary={"layer_case_ids": {"easy": ["easy_a", "easy_b"], "hard": ["hard_a", "hard_b"]}},
            medium_admission_summary={"admitted_case_ids": ["med_a", "med_b"]},
            positive_solvability_summary={"missing_positive_source_count": 0},
        )
        dev = set(summary["split_case_ids"]["dev"])
        holdout = set(summary["split_case_ids"]["holdout"])
        self.assertFalse(dev & holdout)
        self.assertEqual(summary["layer_counts"]["medium"], 2)

    def test_split_plan_remains_provisional_when_hard_solvability_is_incomplete(self) -> None:
        summary = build_benchmark_split_plan(
            relayer_summary={"layer_case_ids": {"easy": ["easy_a"], "hard": ["hard_a"]}},
            medium_admission_summary={"admitted_case_ids": ["med_a"]},
            positive_solvability_summary={"missing_positive_source_count": 1},
        )
        self.assertEqual(summary["status"], "REVIEW")
        self.assertIn("hard_positive_solvability_incomplete", summary["gaps"])
        self.assertFalse(summary["holdout_policy"]["may_drive_agent_tuning"])

    def test_run_split_plan_writes_split_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relayer = root / "relayer.json"
            medium = root / "medium.json"
            positive = root / "positive.json"
            relayer.write_text('{"layer_case_ids":{"easy":["easy_a"],"hard":["hard_a"]}}', encoding="utf-8")
            medium.write_text('{"admitted_case_ids":["med_a"]}', encoding="utf-8")
            positive.write_text('{"missing_positive_source_count":0}', encoding="utf-8")
            out = root / "out"
            summary = run_benchmark_split_plan(
                relayer_path=relayer,
                medium_admission_path=medium,
                positive_solvability_path=positive,
                out_dir=out,
            )
            self.assertTrue((out / "dev_case_ids.txt").exists())
            self.assertTrue((out / "holdout_case_ids.txt").exists())
            self.assertEqual(summary["split_counts"]["train_candidate"], 0)


if __name__ == "__main__":
    unittest.main()
