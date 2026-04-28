from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_structure_plan_checkpoint_summary_v0_30_10 import (
    build_structure_plan_checkpoint_summary,
)


def _write(path: Path, *, verdict: str, strategy: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    calls = []
    if strategy:
        calls.append(
            {
                "name": "record_structure_strategies",
                "arguments": {"strategies": ["a", "b"], "selected_strategy": "a"},
            }
        )
    calls.append({"name": "check_model", "arguments": {"model_text": "model X end X;"}})
    row = {
        "case_id": "sem_case",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [{"step": 1, "tool_calls": calls, "tool_results": [{"name": "check_model", "result": "Failed"}]}],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class StructurePlanCheckpointSummaryV03010Tests(unittest.TestCase):
    def test_summary_reports_invoked_without_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write(run_dir, verdict="FAILED", strategy=True)
            summary = build_structure_plan_checkpoint_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["strategy_call_count"], 1)
            self.assertEqual(summary["decision"], "structure_plan_invoked_without_discovery_gain")


if __name__ == "__main__":
    unittest.main()
