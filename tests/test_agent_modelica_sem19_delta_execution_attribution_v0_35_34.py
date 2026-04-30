from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_sem19_delta_execution_attribution_v0_35_34 import (
    TARGET_CASE_ID,
    build_sem19_delta_execution_attribution,
)


class Sem19DeltaExecutionAttributionV03534Tests(unittest.TestCase):
    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_sem19_delta_execution_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")

    def test_detects_no_residual_matching_candidate(self) -> None:
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
                                    "compiler_named_residual_count": 2,
                                    "candidates": [
                                        {"strategy": "a", "expected_equation_delta": 4, "rationale": "r"}
                                    ],
                                    "selected_strategy": "a",
                                },
                            }
                        ],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_sem19_delta_execution_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "sem19_no_residual_matching_candidate")


if __name__ == "__main__":
    unittest.main()
