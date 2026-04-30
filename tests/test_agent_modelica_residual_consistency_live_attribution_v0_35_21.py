from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_residual_consistency_live_attribution_v0_35_21 import (
    build_residual_consistency_live_attribution,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class ResidualConsistencyLiveAttributionV03521Tests(unittest.TestCase):
    def test_detects_consistency_tool_usage_without_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": TARGET_CASE_ID,
                "tool_profile": "connector_flow_residual_consistency_checkpoint",
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 2,
                        "tool_calls": [{"name": "residual_hypothesis_consistency_check", "arguments": {}}],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_residual_consistency_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["consistency_tool_used_count"], 1)
            self.assertEqual(summary["decision"], "residual_consistency_discoverable_but_no_sem22_pass")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_residual_consistency_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
