from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_submit_checkpoint_attribution_v0_34_16 import (
    build_connector_flow_submit_checkpoint_attribution,
)


def _write_run(root: Path, *, include_success: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X.mat"' if include_success else 'Class X has 24 equation(s) and 24 variable(s). resultFile = ""'
    row = {
        "case_id": "case_a",
        "final_verdict": "FAILED",
        "submitted": False,
        "provider_error": "",
        "step_count": 2,
        "token_used": 10,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "connector_flow_semantics_diagnostic"}],
                "tool_results": [{"name": "connector_flow_semantics_diagnostic", "result": "{}"}],
            },
            {
                "step": 2,
                "tool_calls": [{"name": "check_model"}],
                "tool_results": [{"name": "check_model", "result": result}],
            },
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ConnectorFlowSubmitCheckpointAttributionV03416Tests(unittest.TestCase):
    def test_detects_diagnostic_without_checkpoint_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir)
            summary = build_connector_flow_submit_checkpoint_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["diagnostic_call_count"], 1)
            self.assertEqual(summary["success_evidence_steps"], [])
            self.assertEqual(summary["balanced_without_success_steps"], [2])
            self.assertEqual(summary["checkpoint_message_count"], 0)
            self.assertEqual(summary["decision"], "flow_diagnostic_invoked_but_submit_checkpoint_not_reached")

    def test_detects_checkpoint_reached_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir, include_success=True)
            summary = build_connector_flow_submit_checkpoint_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["success_evidence_steps"], [2])
            self.assertEqual(summary["decision"], "submit_checkpoint_reached_success_evidence")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_submit_checkpoint_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
