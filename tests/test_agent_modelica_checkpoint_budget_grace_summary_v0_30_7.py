from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_checkpoint_budget_grace_summary_v0_30_7 import (
    build_checkpoint_budget_grace_summary,
)


def _write(path: Path, *, case_id: str, verdict: str, success_seen: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X_res.mat"' if success_seen else "Failed to build model"
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    with (path / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class CheckpointBudgetGraceSummaryV0307Tests(unittest.TestCase):
    def test_summary_reports_positive_signal_for_three_passes_without_discovery_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write(run_dir, case_id="sem_a", verdict="PASS", success_seen=True)
            _write(run_dir, case_id="sem_b", verdict="PASS", success_seen=True)
            _write(run_dir, case_id="sem_c", verdict="PASS", success_seen=True)
            _write(run_dir, case_id="sem_d", verdict="FAILED", success_seen=True)
            summary = build_checkpoint_budget_grace_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["version"], "v0.30.7")
            self.assertEqual(summary["decision"], "checkpoint_budget_grace_positive_signal")


if __name__ == "__main__":
    unittest.main()
