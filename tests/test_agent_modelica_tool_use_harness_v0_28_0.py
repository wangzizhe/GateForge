from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_tool_use_harness_v0_28_0 import (
    BASE_TOOL_DEFS,
    TOOL_DEFS,
    dispatch_tool,
    get_tool_defs,
    get_tool_profile_guidance,
    run_tool_use_baseline,
    run_tool_use_case,
)
from gateforge.agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import BUILTIN_CASES
from gateforge.llm_provider_adapter import LLMProviderConfig, ToolCall, ToolResponse


class _SubmitAdapter:
    def send_tool_request(self, messages, tools, config):  # type: ignore[no-untyped-def]
        return (
            ToolResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="submit_final",
                        arguments={"model_text": "model X\n  Real x;\nequation\n  x = 1;\nend X;"},
                    )
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 10},
            ),
            "",
        )


class ToolUseHarnessV0280Tests(unittest.TestCase):
    def test_tool_defs_have_basic_tools(self) -> None:
        names = {t["name"] for t in TOOL_DEFS}
        self.assertIn("check_model", names)
        self.assertIn("simulate_model", names)
        self.assertIn("submit_final", names)

    def test_base_tool_profile_excludes_structural_tools(self) -> None:
        base_names = {t["name"] for t in BASE_TOOL_DEFS}
        resolved_names = {t["name"] for t in get_tool_defs("base")}
        self.assertEqual(base_names, resolved_names)
        self.assertNotIn("get_unmatched_vars", resolved_names)

    def test_connector_profile_guidance_mentions_diagnostic_tool(self) -> None:
        guidance = get_tool_profile_guidance("connector")
        self.assertIn("connector_balance_diagnostic", guidance)
        self.assertEqual(get_tool_profile_guidance("base"), "")

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

    def test_submit_final_step_is_recorded(self) -> None:
        case = {
            "case_id": "submit_case",
            "model_name": "X",
            "model_text": "model X\n  Real x;\nequation\nend X;",
            "workflow_goal": "Fix the model.",
        }
        with patch(
            "gateforge.agent_modelica_tool_use_harness_v0_28_0.resolve_provider_adapter",
            return_value=(_SubmitAdapter(), LLMProviderConfig(provider_name="fake", model="fake", api_key="fake")),
        ), patch(
            "gateforge.agent_modelica_tool_use_harness_v0_28_0._run_omc",
            return_value=(0, "ok", True, True),
        ):
            result = run_tool_use_case(case, max_steps=1, max_token_budget=8000, planner_backend="fake")
        self.assertEqual(result["final_verdict"], "PASS")
        self.assertEqual(result["steps"][0]["tool_calls"][0]["name"], "submit_final")

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
