from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_portfolio_attribution_v0_35_7 import (
    build_candidate_portfolio_attribution,
)


class CandidatePortfolioAttributionV0357Tests(unittest.TestCase):
    def test_detects_no_discovery_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": "case_a",
                "final_verdict": "FAILED",
                "submitted": False,
                "provider_error": "",
                "step_count": 1,
                "token_used": 5,
                "steps": [
                    {
                        "step": 1,
                        "tool_calls": [{"name": "check_model"}],
                        "tool_results": [{"name": "check_model", "result": "check failed"}],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_candidate_portfolio_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["success_candidate_seen_count"], 0)
            self.assertEqual(summary["decision"], "candidate_portfolio_prompt_does_not_improve_discovery")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_candidate_portfolio_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
