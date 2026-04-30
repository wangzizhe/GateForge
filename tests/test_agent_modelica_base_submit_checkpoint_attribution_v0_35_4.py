from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_base_submit_checkpoint_attribution_v0_35_4 import (
    build_base_submit_checkpoint_attribution,
)


class BaseSubmitCheckpointAttributionV0354Tests(unittest.TestCase):
    def test_detects_checkpoint_converted_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": "case_a",
                "final_verdict": "PASS",
                "submitted": True,
                "provider_error": "",
                "step_count": 2,
                "token_used": 5,
                "steps": [
                    {
                        "step": 1,
                        "checkpoint_messages": ["Transparent checkpoint"],
                        "tool_calls": [{"name": "check_model"}],
                        "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/X.mat"'}],
                    },
                    {
                        "step": 2,
                        "tool_calls": [{"name": "submit_final"}],
                        "tool_results": [{"name": "submit_final", "result": '{"status":"submitted"}'}],
                    },
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_base_submit_checkpoint_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["checkpoint_message_count"], 1)
            self.assertEqual(summary["decision"], "base_submit_checkpoint_converts_success_candidate_to_pass")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_base_submit_checkpoint_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
