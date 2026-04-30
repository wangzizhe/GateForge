from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_arrayed_bus_live_attribution_v0_35_19 import build_arrayed_bus_live_attribution
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class ArrayedBusLiveAttributionV03519Tests(unittest.TestCase):
    def test_detects_discoverable_but_failed_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": TARGET_CASE_ID,
                "tool_profile": "connector_flow_arrayed_bus_checkpoint",
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 2,
                        "tool_calls": [{"name": "arrayed_shared_bus_diagnostic", "arguments": {}}],
                        "tool_results": [{"name": "arrayed_shared_bus_diagnostic", "result": "{}"}],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_arrayed_bus_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["arrayed_tool_used_count"], 1)
            self.assertEqual(summary["decision"], "arrayed_bus_diagnostic_discoverable_but_no_sem22_pass")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_arrayed_bus_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
