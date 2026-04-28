from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_checkpoint_repeatability_v0_30_4 import (
    build_candidate_checkpoint_repeatability_summary,
)


def _write(path: Path, *, case_id: str, verdict: str, checkpoint_count: int = 0) -> None:
    path.mkdir(parents=True, exist_ok=True)
    step = {
        "step": 1,
        "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
        "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/X_res.mat"'}],
    }
    if checkpoint_count:
        step["checkpoint_messages"] = ["Transparent checkpoint"] * checkpoint_count
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [step],
    }
    with (path / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class CandidateCheckpointRepeatabilityV0304Tests(unittest.TestCase):
    def test_summary_reports_unstable_positive_when_pass_counts_vary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            run_2 = root / "run_2"
            _write(run_1, case_id="sem_a", verdict="PASS", checkpoint_count=1)
            _write(run_1, case_id="sem_b", verdict="PASS", checkpoint_count=1)
            _write(run_2, case_id="sem_a", verdict="PASS", checkpoint_count=1)
            _write(run_2, case_id="sem_b", verdict="FAILED", checkpoint_count=0)
            summary = build_candidate_checkpoint_repeatability_summary(
                run_dirs={"run_1": run_1, "run_2": run_2},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "checkpoint_positive_but_unstable")
            self.assertEqual(summary["run_pass_counts"], [2, 1])
            self.assertEqual(summary["mixed_case_count"], 1)

    def test_summary_reports_stable_positive_when_all_runs_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            run_2 = root / "run_2"
            for run in (run_1, run_2):
                for case_id in ("sem_a", "sem_b", "sem_c"):
                    _write(run, case_id=case_id, verdict="PASS", checkpoint_count=1)
            summary = build_candidate_checkpoint_repeatability_summary(
                run_dirs={"run_1": run_1, "run_2": run_2},
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "checkpoint_repeatability_stable_positive")
            self.assertEqual(summary["stable_pass_case_count"], 3)


if __name__ == "__main__":
    unittest.main()
