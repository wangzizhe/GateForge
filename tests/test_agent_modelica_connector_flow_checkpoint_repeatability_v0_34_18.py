from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_checkpoint_repeatability_v0_34_18 import (
    build_connector_flow_checkpoint_repeatability,
)


def _write_run(root: Path, *, success: bool, checkpoint: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X.mat"' if success else 'Class X has 24 equation(s) and 24 variable(s). resultFile = ""'
    step = {
        "step": 1,
        "tool_calls": [{"name": "check_model"}],
        "tool_results": [{"name": "check_model", "result": result}],
    }
    if checkpoint:
        step["checkpoint_messages"] = ["checkpoint"]
    row = {
        "case_id": "case_a",
        "final_verdict": "FAILED",
        "submitted": False,
        "provider_error": "",
        "step_count": 1,
        "token_used": 10,
        "steps": [step],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ConnectorFlowCheckpointRepeatabilityV03418Tests(unittest.TestCase):
    def test_detects_checkpoint_not_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            _write_run(run, success=False)
            summary = build_connector_flow_checkpoint_repeatability(run_dirs=[run], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["success_candidate_seen_count"], 0)
            self.assertEqual(summary["checkpoint_message_count"], 0)
            self.assertEqual(summary["decision"], "connector_flow_checkpoint_not_reached_candidate_discovery_unstable")

    def test_detects_checkpoint_triggered_without_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            _write_run(run, success=True, checkpoint=True)
            summary = build_connector_flow_checkpoint_repeatability(run_dirs=[run], out_dir=root / "out")
            self.assertEqual(summary["success_candidate_seen_count"], 1)
            self.assertEqual(summary["checkpoint_message_count"], 1)
            self.assertEqual(summary["decision"], "connector_flow_checkpoint_triggered_without_pass")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_checkpoint_repeatability(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
