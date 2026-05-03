from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_v1_relayer_v0_52_0 import (
    build_benchmark_v1_relayer,
    run_benchmark_v1_relayer,
)


class BenchmarkV1RelayerV052Tests(unittest.TestCase):
    def test_relayer_keeps_hard_pack_but_flags_missing_medium_layer(self) -> None:
        summary = build_benchmark_v1_relayer(
            hard_pack_summary={
                "hard_case_ids": ["hard_a", "hard_b"],
                "easy_calibration_case_ids": ["easy_a"],
                "unstable_case_ids": ["unstable_a"],
            },
            comparison_baseline_summary={
                "pass_case_ids": ["easy_b"],
                "fail_case_ids": ["hard_a", "unstable_a"],
            },
        )
        self.assertEqual(summary["layer_counts"]["hard"], 2)
        self.assertEqual(summary["layer_counts"]["easy"], 2)
        self.assertIn("missing_medium_layer", summary["gaps"])
        self.assertIn("hard_pack_cannot_be_sole_comparison_set", summary["gaps"])
        self.assertFalse(summary["conclusion_allowed"])

    def test_relayer_reports_unclassified_baseline_failures(self) -> None:
        summary = build_benchmark_v1_relayer(
            hard_pack_summary={"hard_case_ids": ["hard_a"], "unstable_case_ids": []},
            comparison_baseline_summary={"pass_case_ids": [], "fail_case_ids": ["unknown_fail"]},
        )
        self.assertEqual(summary["unclassified_baseline_failure_ids"], ["unknown_fail"])
        self.assertIn("unclassified_baseline_failures", summary["gaps"])

    def test_run_relayer_writes_layer_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hard = root / "hard.json"
            baseline = root / "baseline.json"
            hard.write_text(
                '{"hard_case_ids":["hard_a"],"easy_calibration_case_ids":["easy_a"],"unstable_case_ids":[]}',
                encoding="utf-8",
            )
            baseline.write_text('{"pass_case_ids":["easy_b"],"fail_case_ids":["hard_a"]}', encoding="utf-8")
            out = root / "out"
            summary = run_benchmark_v1_relayer(hard_pack_path=hard, comparison_baseline_path=baseline, out_dir=out)
            self.assertEqual(summary["layer_counts"]["hard"], 1)
            self.assertTrue((out / "hard_case_ids.txt").exists())
            self.assertTrue((out / "medium_case_ids.txt").exists())


if __name__ == "__main__":
    unittest.main()
