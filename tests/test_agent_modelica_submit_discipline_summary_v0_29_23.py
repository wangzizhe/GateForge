from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_submit_discipline_summary_v0_29_23 import build_submit_discipline_summary
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


def _write(path: Path, *, verdict: str, submitted: bool, successful_tool: bool) -> None:
    path.mkdir(parents=True)
    result = 'resultFile = "/workspace/X_res.mat"' if successful_tool else "Failed to build model"
    row = {
        "case_id": "sem_case",
        "final_verdict": verdict,
        "submitted": submitted,
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SubmitDisciplineSummaryV02923Tests(unittest.TestCase):
    def test_build_summary_reports_fixed_missed_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, verdict="FAILED", submitted=False, successful_tool=True)
            _write(probe, verdict="PASS", submitted=True, successful_tool=True)
            summary = build_submit_discipline_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "submit_discipline_positive_signal")
            self.assertEqual(summary["missed_success_fixed_count"], 1)
            self.assertTrue((root / "out" / "summary.json").exists())

    def test_submit_discipline_profile_is_exposed(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_submit_discipline")}
        self.assertIn("replaceable_partial_diagnostic", names)
        self.assertIn("replaceable_partial_policy_check", names)
        self.assertIn("submit discipline", get_tool_profile_guidance("replaceable_policy_submit_discipline"))


if __name__ == "__main__":
    unittest.main()
