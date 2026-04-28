from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_checkpoint_summary_v0_30_3 import build_candidate_checkpoint_summary


def _write(
    path: Path,
    *,
    verdict: str,
    submitted: bool,
    successful_tool: bool,
    checkpoint_count: int,
) -> None:
    path.mkdir(parents=True)
    result = 'resultFile = "/workspace/X_res.mat"' if successful_tool else "Failed to build model"
    step = {
        "step": 1,
        "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
        "tool_results": [{"name": "check_model", "result": result}],
    }
    if checkpoint_count:
        step["checkpoint_messages"] = ["Transparent checkpoint"] * checkpoint_count
    row = {
        "case_id": "sem_case",
        "final_verdict": verdict,
        "submitted": submitted,
        "token_used": 1000,
        "steps": [step],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class CandidateCheckpointSummaryV0303Tests(unittest.TestCase):
    def test_summary_reports_positive_signal_when_missed_success_is_fixed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, verdict="FAILED", submitted=False, successful_tool=True, checkpoint_count=0)
            _write(probe, verdict="PASS", submitted=True, successful_tool=True, checkpoint_count=1)
            summary = build_candidate_checkpoint_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "transparent_checkpoint_positive_signal")
            self.assertEqual(summary["probe_checkpoint_count"], 1)
            self.assertEqual(summary["missed_success_fixed_count"], 1)

    def test_summary_requires_checkpoint_trigger_for_checkpoint_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, verdict="FAILED", submitted=False, successful_tool=True, checkpoint_count=0)
            _write(probe, verdict="PASS", submitted=True, successful_tool=True, checkpoint_count=0)
            summary = build_candidate_checkpoint_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "checkpoint_not_triggered")


if __name__ == "__main__":
    unittest.main()
