from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_submit_checkpoint_attribution_v0_34_14 import (
    build_submit_checkpoint_attribution,
)


def _write_run(root: Path, *, result_text: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": "case_a",
        "final_verdict": "FAILED",
        "submitted": False,
        "provider_error": "",
        "step_count": 1,
        "token_used": 10,
        "steps": [
            {
                "step": 1,
                "text": "step",
                "tool_calls": [{"name": "check_model"}],
                "tool_results": [{"name": "check_model", "result": result_text}],
            }
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SubmitCheckpointAttributionV03414Tests(unittest.TestCase):
    def test_detects_balanced_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir, result_text="Class X has 24 equation(s) and 24 variable(s). resultFile = \"\"")
            summary = build_submit_checkpoint_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["balanced_candidate_steps"], [1])
            self.assertEqual(summary["success_evidence_steps"], [])
            self.assertEqual(summary["decision"], "balanced_candidate_seen_without_simulation_success")

    def test_detects_success_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir, result_text='resultFile = "/workspace/X.mat"')
            summary = build_submit_checkpoint_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["success_evidence_steps"], [1])
            self.assertEqual(summary["decision"], "submit_checkpoint_reached_success_evidence")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_submit_checkpoint_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
