from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_omc_named_live_attribution_v0_35_20 import build_omc_named_live_attribution
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class OmcNamedLiveAttributionV03520Tests(unittest.TestCase):
    def test_detects_omc_named_tool_usage_without_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": TARGET_CASE_ID,
                "tool_profile": "connector_flow_omc_named_checkpoint",
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 2,
                        "tool_calls": [{"name": "omc_unmatched_flow_diagnostic", "arguments": {}}],
                        "tool_results": [{"name": "omc_unmatched_flow_diagnostic", "result": "{}"}],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_omc_named_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["omc_named_tool_used_count"], 1)
            self.assertEqual(summary["decision"], "omc_named_residual_diagnostic_discoverable_but_no_sem22_pass")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_omc_named_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
