from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_v1_refreeze_closeout_v0_60_4 import (
    build_benchmark_v1_refreeze_closeout,
    run_benchmark_v1_refreeze_closeout,
)


class BenchmarkV1RefreezeCloseoutV060Tests(unittest.TestCase):
    def test_refreeze_ready_when_solvable_layers_exist(self) -> None:
        summary = build_benchmark_v1_refreeze_closeout(
            split_summary={"status": "PASS", "layer_counts": {"easy": 1, "medium": 2, "hard_solvable": 3}},
            bundle_summary={"status": "PASS", "task_count": 6},
        )
        self.assertTrue(summary["freeze_ready"])
        self.assertFalse(summary["freeze_scope"]["frontier_counts_in_primary_score"])

    def test_refreeze_blocks_missing_medium(self) -> None:
        summary = build_benchmark_v1_refreeze_closeout(
            split_summary={"status": "PASS", "layer_counts": {"easy": 1, "medium": 0, "hard_solvable": 3}},
            bundle_summary={"status": "PASS", "task_count": 6},
        )
        self.assertFalse(summary["freeze_ready"])
        self.assertIn("missing_medium_layer", summary["blockers"])

    def test_run_refreeze_closeout_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split = root / "split.json"
            bundle = root / "bundle.json"
            split.write_text('{"status":"PASS","layer_counts":{"easy":1,"medium":1,"hard_solvable":1},"split_counts":{}}', encoding="utf-8")
            bundle.write_text('{"status":"PASS","task_count":3}', encoding="utf-8")
            out = root / "out"
            summary = run_benchmark_v1_refreeze_closeout(split_path=split, bundle_path=bundle, out_dir=out)
            self.assertTrue(summary["freeze_ready"])
            self.assertTrue((out / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
