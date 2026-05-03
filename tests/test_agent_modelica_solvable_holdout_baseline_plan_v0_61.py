from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_solvable_holdout_baseline_plan_v0_61_1 import (
    build_solvable_holdout_baseline_plan,
    run_solvable_holdout_baseline_plan,
)


class SolvableHoldoutBaselinePlanV061Tests(unittest.TestCase):
    def test_plan_requires_bundle_holdout_count_match(self) -> None:
        summary = build_solvable_holdout_baseline_plan(
            split_summary={"split_case_ids": {"holdout": ["case_a", "case_b"]}},
            bundle_summary={"status": "PASS", "holdout_task_count": 1},
        )
        self.assertIn("bundle_holdout_count_mismatch", summary["gaps"])
        self.assertEqual(summary["status"], "REVIEW")

    def test_plan_is_ready_with_holdout_and_matching_bundle(self) -> None:
        summary = build_solvable_holdout_baseline_plan(
            split_summary={"split_case_ids": {"holdout": ["case_a"]}},
            bundle_summary={"status": "PASS", "holdout_task_count": 1},
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["run_contract"]["provider"], "env")
        self.assertTrue(summary["run_contract"]["frontier_cases_excluded"])

    def test_run_plan_writes_holdout_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split = root / "split.json"
            bundle = root / "bundle.json"
            split.write_text('{"split_case_ids":{"holdout":["case_a"]}}', encoding="utf-8")
            bundle.write_text('{"status":"PASS","holdout_task_count":1}', encoding="utf-8")
            out = root / "out"
            summary = run_solvable_holdout_baseline_plan(split_path=split, bundle_path=bundle, out_dir=out)
            self.assertEqual(summary["holdout_case_ids"], ["case_a"])
            self.assertTrue((out / "holdout_case_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
