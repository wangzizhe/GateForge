from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_harness_regression_ab_v0_26_4 import (
    build_harness_regression_ab,
    compare_metrics,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class HarnessRegressionABV0264Tests(unittest.TestCase):
    def test_compare_metrics_preserves_pass_rate_and_flags_fake_multiturn(self) -> None:
        rows = [
            {
                "run_id": "r1",
                "case_id": "true_multi",
                "final_verdict": "PASS",
                "executor_attempt_count": 3,
                "repair_round_count": 2,
            },
            {
                "run_id": "r1",
                "case_id": "fake_multi",
                "final_verdict": "PASS",
                "executor_attempt_count": 2,
                "repair_round_count": 1,
            },
            {
                "run_id": "r1",
                "case_id": "failed",
                "final_verdict": "FAILED",
                "executor_attempt_count": 3,
                "repair_round_count": 2,
            },
        ]
        comparison = compare_metrics(rows)
        self.assertEqual(comparison["pass_count_delta"], 0)
        self.assertEqual(comparison["pass_rate_delta"], 0.0)
        self.assertEqual(comparison["fake_multiturn_row_count"], 1)
        self.assertEqual(comparison["multiturn_count_delta"], -1)

    def test_build_harness_regression_ab_uses_real_shape_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "normalized.jsonl"
            _write_jsonl(
                input_path,
                [
                    {
                        "run_id": "r1",
                        "case_id": "c1",
                        "final_verdict": "PASS",
                        "executor_attempt_count": 3,
                        "repair_round_count": 2,
                    }
                ],
            )
            summary = build_harness_regression_ab(input_path=input_path, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["capability_metric_changed"])
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "comparison.json").exists())

    def test_missing_input_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_harness_regression_ab(
                input_path=Path(tmp) / "missing.jsonl",
                out_dir=Path(tmp) / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
