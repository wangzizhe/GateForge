from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_delta_portfolio_live_attribution_v0_35_26 import (
    build_delta_portfolio_live_attribution,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class DeltaPortfolioLiveAttributionV03526Tests(unittest.TestCase):
    def test_detects_residual_delta_coverage_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            portfolio = {
                "candidate_count": 2,
                "distinct_delta_count": 2,
                "has_residual_matching_delta": True,
                "expected_equation_deltas": [6, 4],
            }
            row = {
                "case_id": TARGET_CASE_ID,
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 1,
                        "tool_results": [
                            {
                                "name": "record_equation_delta_candidate_portfolio",
                                "result": json.dumps(portfolio),
                            }
                        ],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_delta_portfolio_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["residual_matching_count"], 1)
            self.assertEqual(summary["decision"], "delta_portfolio_covered_residual_delta_without_success")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_delta_portfolio_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
