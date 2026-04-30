from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_residual_obedience_attribution_v0_35_22 import (
    build_residual_obedience_attribution,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class ResidualObedienceAttributionV03522Tests(unittest.TestCase):
    def test_detects_acknowledged_but_violated_consistency(self) -> None:
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
                        "tool_calls": [{"name": "residual_hypothesis_consistency_check", "arguments": {}}],
                    },
                    {
                        "step": 2,
                        "text": "The consistency check says the delta of 6 exceeds the 4 compiler-named residuals.",
                        "tool_calls": [
                            {
                                "name": "check_model",
                                "arguments": {
                                    "model_text": "model X equation p[1].i = 0; p[2].i = 0; p[3].i = 0; n[1].i = 0; n[2].i = 0; n[3].i = 0; end X;"
                                },
                            }
                        ],
                    },
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_residual_obedience_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["mismatch_acknowledged_count"], 1)
            self.assertEqual(summary["post_consistency_violation_count"], 1)
            self.assertEqual(summary["decision"], "residual_critique_acknowledged_but_not_obeyed")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_residual_obedience_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
