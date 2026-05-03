from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_split_rebuild_v0_60_3 import build_benchmark_split_rebuild, run_benchmark_split_rebuild


class BenchmarkSplitRebuildV060Tests(unittest.TestCase):
    def test_rebuild_moves_unresolved_cases_to_frontier(self) -> None:
        summary = build_benchmark_split_rebuild(
            relayer_summary={"layer_case_ids": {"easy": ["easy_a", "easy_b"]}},
            medium_summary={"admitted_case_ids": ["med_a", "med_b"]},
            positive_summary={"positive_source_case_ids": ["hard_a", "hard_b"]},
            resolution_summary={"frontier_unresolved_case_ids": ["frontier_a"], "near_miss_reference_queue_case_ids": ["near_a"]},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["layer_counts"]["frontier"], 1)
        self.assertFalse(summary["policy"]["frontier_counts_in_solvable_scoring"])
        self.assertIn("frontier_a", summary["split_case_ids"]["frontier"])

    def test_run_rebuild_writes_split_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relayer = root / "relayer.json"
            medium = root / "medium.json"
            positive = root / "positive.json"
            resolution = root / "resolution.json"
            relayer.write_text('{"layer_case_ids":{"easy":["easy_a"],"hard":["hard_a"]}}', encoding="utf-8")
            medium.write_text('{"admitted_case_ids":["med_a"]}', encoding="utf-8")
            positive.write_text('{"positive_source_case_ids":["hard_a"]}', encoding="utf-8")
            resolution.write_text('{"frontier_unresolved_case_ids":["frontier_a"],"near_miss_reference_queue_case_ids":[]}', encoding="utf-8")
            out = root / "out"
            summary = run_benchmark_split_rebuild(
                relayer_path=relayer,
                medium_path=medium,
                positive_path=positive,
                resolution_path=resolution,
                out_dir=out,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out / "frontier_case_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
