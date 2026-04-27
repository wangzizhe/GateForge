from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_tool_use_harness_v0_28_0 import (
    TOOL_DEFS,
    dispatch_tool,
    run_tool_use_baseline,
    run_tool_use_case,
)
from gateforge.agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import BUILTIN_CASES


class ToolUseHarnessV0280Tests(unittest.TestCase):
    def test_tool_defs_have_basic_tools(self) -> None:
        names = {t["name"] for t in TOOL_DEFS}
        self.assertIn("check_model", names)
        self.assertIn("simulate_model", names)
        self.assertIn("submit_final", names)

    def test_dispatch_unknown_tool_returns_error(self) -> None:
        result = dispatch_tool("nonexistent", {})
        self.assertIn("error", result)

    def test_dispatch_submit_final_returns_ack(self) -> None:
        result = dispatch_tool("submit_final", {"model_text": "model X end X;"})
        self.assertIn("submitted", result)

    def test_run_tool_use_case_with_rule_backend_fails(self) -> None:
        case = BUILTIN_CASES[0].copy()
        result = run_tool_use_case(case, max_steps=5, max_token_budget=8000, planner_backend="rule")
        self.assertEqual(result["final_verdict"], "FAILED")
        self.assertIn("rule_backend", result["provider_error"])

    def test_run_tool_use_baseline_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = run_tool_use_baseline(
                out_dir=out_dir,
                cases=BUILTIN_CASES[:1],
                limit=1,
                max_steps=5,
                max_token_budget=8000,
                planner_backend="rule",
            )
            self.assertEqual(summary["case_count"], 1)
            self.assertEqual(summary["pass_count"], 0)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "results.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
