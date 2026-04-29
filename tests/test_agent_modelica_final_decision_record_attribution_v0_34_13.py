from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_final_decision_record_attribution_v0_34_13 import (
    build_final_decision_record_attribution,
)


def _write_run(root: Path, *, tools: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    steps = []
    for index, tool in enumerate(tools, start=1):
        result = 'resultFile = "/workspace/X.mat"' if tool == "simulate_model" else "{}"
        steps.append(
            {
                "step": index,
                "text": "step",
                "tool_calls": [{"name": tool}],
                "tool_results": [{"name": tool, "result": result}],
            }
        )
    row = {
        "case_id": "case_a",
        "final_verdict": "FAILED",
        "submitted": False,
        "provider_error": "",
        "token_used": 10,
        "step_count": len(steps),
        "steps": steps,
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class FinalDecisionRecordAttributionV03413Tests(unittest.TestCase):
    def test_detects_record_tool_not_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir, tools=["check_model", "check_model"])
            summary = build_final_decision_record_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "record_tool_trigger_not_reached")
            self.assertEqual(summary["record_call_count"], 0)

    def test_detects_success_without_record_or_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir, tools=["simulate_model"])
            summary = build_final_decision_record_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "success_candidate_seen_but_oracle_and_record_not_used")

    def test_detects_record_tool_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_run(run_dir, tools=["simulate_model", "record_final_decision_rationale"])
            summary = build_final_decision_record_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "final_decision_record_used")


if __name__ == "__main__":
    unittest.main()
