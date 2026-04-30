from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_delta_execution_live_attribution_v0_35_28 import (
    build_delta_execution_live_attribution,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class DeltaExecutionLiveAttributionV03528Tests(unittest.TestCase):
    def test_detects_no_residual_delta_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": TARGET_CASE_ID,
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 1,
                        "tool_calls": [
                            {
                                "name": "record_equation_delta_candidate_portfolio",
                                "arguments": {
                                    "compiler_named_residual_count": 4,
                                    "candidates": [
                                        {"strategy": "a", "expected_equation_delta": 6, "rationale": "r"}
                                    ],
                                    "selected_strategy": "a",
                                },
                            }
                        ],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_delta_execution_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "delta_execution_no_residual_delta_coverage")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_delta_execution_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
