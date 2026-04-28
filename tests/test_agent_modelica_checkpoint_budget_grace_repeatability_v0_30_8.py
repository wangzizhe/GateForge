from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_checkpoint_budget_grace_repeatability_v0_30_8 import (
    build_checkpoint_budget_grace_repeatability,
)


def _write(path: Path, *, case_id: str, verdict: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X_res.mat"' if verdict == "PASS" else "Failed to build model"
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


class CheckpointBudgetGraceRepeatabilityV0308Tests(unittest.TestCase):
    def test_summary_reports_unstable_positive_when_run_pass_counts_vary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            run_2 = root / "run_2"
            for case_id in ("a", "b", "c"):
                _write(run_1, case_id=case_id, verdict="PASS")
            _write(run_2, case_id="a", verdict="PASS")
            _write(run_2, case_id="b", verdict="FAILED")
            _write(run_2, case_id="c", verdict="FAILED")
            summary = build_checkpoint_budget_grace_repeatability(
                run_dirs={"run_1": run_1, "run_2": run_2},
                out_dir=root / "out",
            )
            self.assertEqual(summary["run_pass_counts"], [3, 1])
            self.assertEqual(summary["decision"], "checkpoint_budget_grace_positive_but_unstable")


if __name__ == "__main__":
    unittest.main()
