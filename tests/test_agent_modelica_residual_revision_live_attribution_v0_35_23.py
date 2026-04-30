from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_residual_revision_live_attribution_v0_35_23 import (
    build_residual_revision_live_attribution,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class ResidualRevisionLiveAttributionV03523Tests(unittest.TestCase):
    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_residual_revision_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")

    def test_failed_violation_marks_not_obeyed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": TARGET_CASE_ID,
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {"step": 1, "tool_calls": [{"name": "residual_hypothesis_consistency_check"}]},
                    {
                        "step": 2,
                        "text": "The consistency check says the delta of 6 exceeds the 4 compiler-named residuals.",
                        "tool_calls": [
                            {
                                "name": "check_model",
                                "arguments": {
                                    "model_text": "model X equation for i in 1:3 loop p[i].i = 0; n[i].i = 0; end for; end X;"
                                },
                            }
                        ],
                    },
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_residual_revision_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "residual_revision_guidance_not_obeyed")

    def test_pass_with_initial_violation_marks_self_correction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": TARGET_CASE_ID,
                "final_verdict": "PASS",
                "submitted": True,
                "steps": [
                    {"step": 1, "tool_calls": [{"name": "residual_hypothesis_consistency_check"}]},
                    {
                        "step": 2,
                        "text": "The consistency check says the delta of 6 exceeds the 4 compiler-named residuals.",
                        "tool_calls": [
                            {
                                "name": "check_model",
                                "arguments": {
                                    "model_text": "model X equation for i in 1:3 loop p[i].i = 0; n[i].i = 0; end for; end X;"
                                },
                            }
                        ],
                    },
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_residual_revision_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "residual_revision_helped_sem22_pass_after_initial_violation")


if __name__ == "__main__":
    unittest.main()
