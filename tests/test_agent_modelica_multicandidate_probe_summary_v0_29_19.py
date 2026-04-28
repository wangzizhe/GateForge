from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multicandidate_probe_summary_v0_29_19 import build_multicandidate_probe_summary
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


def _write_result(path: Path) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": "sem_06",
        "final_verdict": "FAILED",
        "submitted": False,
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "text": "Try one candidate.",
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X equation x=1; end X;"}}],
            },
            {
                "step": 2,
                "text": "Try another partial base flow equation candidate.",
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X equation x=2; end X;"}}],
            },
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def _write_pass_result(path: Path) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": "sem_07",
        "final_verdict": "PASS",
        "submitted": True,
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "text": "Try one candidate.",
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X equation x=1; end X;"}}],
            },
            {
                "step": 2,
                "text": "Try another candidate.",
                "tool_calls": [{"name": "submit_final", "arguments": {"model_text": "model X equation x=2; end X;"}}],
            },
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class MulticandidateProbeSummaryV02919Tests(unittest.TestCase):
    def test_build_summary_reports_multicandidate_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_result(run_dir)
            summary = build_multicandidate_probe_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "multicandidate_behavior_observed_without_success")
            self.assertEqual(summary["multicandidate_case_count"], 1)
            self.assertTrue((root / "out" / "summary.json").exists())

    def test_build_summary_reports_positive_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_pass_result(run_dir)
            summary = build_multicandidate_probe_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "multicandidate_positive_signal_needs_repeatability")
            self.assertEqual(summary["pass_count"], 1)

    def test_multicandidate_profile_exposes_policy_tools(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_multicandidate")}
        self.assertIn("replaceable_partial_diagnostic", names)
        self.assertIn("replaceable_partial_policy_check", names)
        self.assertIn("multi-candidate", get_tool_profile_guidance("replaceable_policy_multicandidate"))


if __name__ == "__main__":
    unittest.main()
