from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_critique_summary_v0_30_0 import build_candidate_critique_summary


def _write(path: Path, *, verdict: str, submitted: bool, successful_tool: bool, critique: bool) -> None:
    path.mkdir(parents=True)
    result = 'resultFile = "/workspace/X_res.mat"' if successful_tool else "Failed to build model"
    calls = [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}]
    if critique:
        calls.append({"name": "candidate_acceptance_critique", "arguments": {"omc_passed": True}})
    row = {
        "case_id": "sem_case",
        "final_verdict": verdict,
        "submitted": submitted,
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "tool_calls": calls,
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class CandidateCritiqueSummaryV0300Tests(unittest.TestCase):
    def test_summary_reports_positive_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, verdict="FAILED", submitted=False, successful_tool=True, critique=False)
            _write(probe, verdict="PASS", submitted=True, successful_tool=True, critique=True)
            summary = build_candidate_critique_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "candidate_critique_positive_signal")
            self.assertEqual(summary["critique_used_count"], 1)
            self.assertTrue((root / "out" / "summary.json").exists())

    def test_summary_requires_tool_invocation_for_positive_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, verdict="FAILED", submitted=False, successful_tool=True, critique=False)
            _write(probe, verdict="PASS", submitted=True, successful_tool=True, critique=False)
            summary = build_candidate_critique_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "candidate_critique_not_invoked")


if __name__ == "__main__":
    unittest.main()
