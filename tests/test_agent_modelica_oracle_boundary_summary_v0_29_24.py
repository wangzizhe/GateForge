from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_oracle_boundary_summary_v0_29_24 import build_oracle_boundary_summary
from gateforge.agent_modelica_tool_use_harness_v0_28_0 import get_tool_defs, get_tool_profile_guidance


def _write(path: Path, *, verdict: str, submitted: bool, successful_tool: bool, text: str) -> None:
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
                "text": text,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class OracleBoundarySummaryV02924Tests(unittest.TestCase):
    def test_build_summary_reports_oracle_boundary_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            probe = root / "probe"
            _write(baseline, verdict="FAILED", submitted=False, successful_tool=True, text="")
            _write(probe, verdict="PASS", submitted=True, successful_tool=True, text="No task constraint is violated.")
            summary = build_oracle_boundary_summary(
                baseline_dir=baseline,
                probe_dir=probe,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "oracle_boundary_positive_signal")
            self.assertTrue(summary["cases"][0]["constraint_citation_seen"])
            self.assertTrue((root / "out" / "summary.json").exists())

    def test_oracle_boundary_profile_is_exposed(self) -> None:
        names = {tool["name"] for tool in get_tool_defs("replaceable_policy_oracle_boundary")}
        self.assertIn("replaceable_partial_diagnostic", names)
        self.assertIn("replaceable_partial_policy_check", names)
        self.assertIn("oracle-boundary", get_tool_profile_guidance("replaceable_policy_oracle_boundary"))


if __name__ == "__main__":
    unittest.main()
