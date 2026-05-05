from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.llm_provider_adapter import LLMProviderConfig, ToolCall, ToolResponse
from gateforge.agent_modelica_subagent_isolation_v0_69_0 import (
    DISPATCH_SUBAGENT_REPAIR_TOOL_DEF,
    SUBAGENT_TOOL_DEFS,
    build_equal_budget_ab_summary,
    build_hard_pack_subagent_readiness_summary,
    build_parallel_subagent_gate_summary,
    build_subagent_isolation_summary,
    dispatch_subagent_repair_mock,
    run_live_subagent_repair,
    run_mock_subagent_repair,
    run_subagent_contract_probe,
)


class SubagentIsolationV069Tests(unittest.TestCase):
    def test_subagent_tool_contract_is_minimal(self) -> None:
        self.assertEqual(DISPATCH_SUBAGENT_REPAIR_TOOL_DEF["name"], "dispatch_subagent_repair")
        tool_names = {tool["name"] for tool in SUBAGENT_TOOL_DEFS}
        self.assertEqual(tool_names, {"write_and_check_candidate_model", "submit_candidate_model"})

    def test_mock_subagent_pass_writes_complete_artifacts(self) -> None:
        case = {"case_id": "case_a", "model_name": "M", "model_text": "model M\nend M;\n"}
        outcome = {
            "subagent_verdict": "PASS",
            "submitted": True,
            "submitted_candidate_id": "candidate_1",
            "token_used": 123,
            "key_findings": "candidate passed",
            "candidates": [
                {
                    "candidate_id": "candidate_1",
                    "model_text": "model M\nend M;\n",
                    "check_ok": True,
                    "simulate_ok": True,
                    "submitted": True,
                    "omc_output": "The simulation finished successfully.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            summary = run_mock_subagent_repair(
                case=case,
                out_dir=Path(td),
                strategy_hint="try isolated fix",
                outcome=outcome,
            )
            artifact_path = Path(summary["artifact_path"])
            result_rows = (artifact_path.parent / "results.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(summary["subagent_verdict"], "PASS")
        self.assertTrue(summary["submitted"])
        self.assertFalse(summary["budget_exceeded"])
        self.assertTrue(summary["artifact_complete"])
        self.assertEqual(len(result_rows), 1)
        self.assertFalse(summary["discipline"]["wrapper_auto_submit_added"])
        self.assertTrue(summary["discipline"]["main_agent_submit_required"])

    def test_dispatch_returns_tool_response_without_candidate_selection(self) -> None:
        case = {"case_id": "case_a", "model_name": "M", "model_text": "model M\nend M;\n"}
        outcome = {
            "subagent_verdict": "FAILED",
            "submitted": False,
            "failure_category": "candidate_generation_failed",
            "candidates": [],
        }
        with tempfile.TemporaryDirectory() as td:
            response = json.loads(dispatch_subagent_repair_mock(
                arguments={"strategy_hint": "try a different topology"},
                case=case,
                out_dir=Path(td),
                outcome=outcome,
            ))

        self.assertEqual(response["subagent_verdict"], "FAILED")
        self.assertFalse(response["submitted"])
        self.assertFalse(response["budget_exceeded"])
        self.assertFalse(response["auto_repair"])
        self.assertFalse(response["auto_submit"])
        self.assertFalse(response["candidate_selected"])
        self.assertTrue(response["artifact_path"])

    def test_pass_subagent_does_not_create_capability_conclusion(self) -> None:
        result = {
            "case_id": "case_a",
            "artifact_complete": True,
            "subagent_count": 1,
            "subagent_pass_count": 1,
            "provider_error_count": 0,
            "timeout_count": 0,
            "main_agent_submitted_subagent_candidate": False,
            "discipline": {
                "deterministic_repair_added": False,
                "hidden_routing_added": False,
                "candidate_selection_added": False,
                "wrapper_auto_submit_added": False,
            },
        }
        summary = build_subagent_isolation_summary(
            case_results=[result],
            case_count=1,
            budget_main=32_000,
            budget_subagents=48_000,
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertFalse(summary["conclusion_allowed"])
        self.assertFalse(summary["capability_conclusion_allowed"])
        self.assertEqual(summary["subagent_pass_count"], 1)
        self.assertFalse(summary["main_agent_submitted_subagent_candidate"])

    def test_summary_blocks_incomplete_artifacts_and_wrapper_flags(self) -> None:
        result = {
            "case_id": "case_a",
            "artifact_complete": False,
            "subagent_count": 1,
            "subagent_pass_count": 1,
            "provider_error_count": 0,
            "timeout_count": 0,
            "discipline": {
                "deterministic_repair_added": False,
                "hidden_routing_added": False,
                "candidate_selection_added": True,
                "wrapper_auto_submit_added": False,
            },
        }
        summary = build_subagent_isolation_summary(case_results=[result], case_count=1)
        self.assertEqual(summary["status"], "REVIEW")
        self.assertFalse(summary["artifact_complete"])
        self.assertFalse(summary["conclusion_allowed"])

    def test_contract_probe_writes_debug_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            summary = run_subagent_contract_probe(out_dir=Path(td))
            written = json.loads((Path(td) / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["evidence_role"], "debug")
        self.assertEqual(written["analysis_scope"], "subagent_isolation_contract")
        self.assertFalse(written["conclusion_allowed"])

    def test_missing_strategy_hint_is_rejected(self) -> None:
        case = {"case_id": "case_a", "model_name": "M", "model_text": "model M\nend M;\n"}
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                run_mock_subagent_repair(
                    case=case,
                    out_dir=Path(td),
                    strategy_hint="",
                    outcome={},
                )

    def test_live_subagent_uses_llm_submit_without_wrapper_selection(self) -> None:
        class FakeAdapter:
            def __init__(self) -> None:
                self.calls = 0

            def send_tool_request(self, messages, tools, config):
                self.calls += 1
                if self.calls == 1:
                    return (
                        ToolResponse(
                            text="write candidate",
                            tool_calls=[
                                ToolCall(
                                    id="call_1",
                                    name="write_and_check_candidate_model",
                                    arguments={
                                        "candidate_id": "candidate_1",
                                        "model_text": "model M\nend M;\n",
                                    },
                                )
                            ],
                            finish_reason="tool_calls",
                            usage={"total_tokens": 10},
                            reasoning="thinking trace",
                        ),
                        "",
                    )
                return (
                    ToolResponse(
                        text="submit candidate",
                        tool_calls=[
                            ToolCall(
                                id="call_2",
                                name="submit_candidate_model",
                                arguments={"candidate_id": "candidate_1"},
                            )
                        ],
                        finish_reason="tool_calls",
                        usage={"total_tokens": 5},
                    ),
                    "",
                )

        config = LLMProviderConfig(provider_name="mock", model="mock", api_key="mock")
        case = {"case_id": "case_a", "model_name": "M", "model_text": "model M\nend M;\n"}
        with tempfile.TemporaryDirectory() as td:
            with patch(
                "gateforge.agent_modelica_subagent_isolation_v0_69_0.resolve_provider_adapter",
                return_value=(FakeAdapter(), config),
            ), patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=("record SimulationResult\nThe simulation finished successfully.", True, True),
            ), patch(
                "gateforge.agent_modelica_subagent_isolation_v0_69_0._run_omc_simulate",
                return_value="record SimulationResult\nThe simulation finished successfully.",
            ):
                summary = run_live_subagent_repair(
                    case=case,
                    out_dir=Path(td),
                    strategy_hint="try one isolated strategy",
                )
                trajectory = json.loads(Path(summary["artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["subagent_verdict"], "PASS")
        self.assertTrue(summary["submitted"])
        self.assertEqual(summary["max_token_budget"], 48_000)
        self.assertFalse(summary["discipline"]["wrapper_auto_submit_added"])
        self.assertFalse(summary["discipline"]["candidate_selection_added"])
        self.assertTrue(summary["artifact_complete"])
        assistant_messages = [msg for msg in trajectory["messages"] if msg.get("role") == "assistant"]
        self.assertEqual(assistant_messages[0]["reasoning_content"], "thinking trace")

    def test_equal_budget_ab_reports_isolation_signal_only_when_subagent_wins(self) -> None:
        summary = build_equal_budget_ab_summary(
            single_agent_summary={
                "pass_count": 0,
                "artifact_complete": True,
                "provider_error_count": 0,
                "harness_timeout_count": 0,
            },
            subagent_summary={
                "subagent_pass_count": 1,
                "artifact_complete": True,
                "provider_error_count": 0,
                "timeout_count": 0,
            },
            budget_total=176_000,
        )
        self.assertTrue(summary["budget_equalized"])
        self.assertTrue(summary["conclusion_allowed"])
        self.assertEqual(summary["decision"], "isolation_gain_candidate")
        self.assertTrue(summary["budget_gain_excluded"])

    def test_equal_budget_ab_blocks_provider_errors(self) -> None:
        summary = build_equal_budget_ab_summary(
            single_agent_summary={
                "pass_count": 0,
                "artifact_complete": True,
                "provider_error_count": 1,
                "harness_timeout_count": 0,
            },
            subagent_summary={
                "subagent_pass_count": 1,
                "artifact_complete": True,
                "provider_error_count": 0,
                "timeout_count": 0,
            },
            budget_total=176_000,
        )
        self.assertFalse(summary["conclusion_allowed"])
        self.assertEqual(summary["decision"], "incomplete_or_provider_blocked")

    def test_equal_budget_ab_blocks_budget_exceeded(self) -> None:
        summary = build_equal_budget_ab_summary(
            single_agent_summary={
                "pass_count": 0,
                "artifact_complete": True,
                "provider_error_count": 0,
                "harness_timeout_count": 0,
            },
            subagent_summary={
                "subagent_pass_count": 1,
                "artifact_complete": True,
                "provider_error_count": 0,
                "timeout_count": 0,
                "budget_exceeded": True,
            },
            budget_total=176_000,
        )
        self.assertFalse(summary["conclusion_allowed"])
        self.assertEqual(summary["budget_exceeded_count"], 1)
        self.assertEqual(summary["decision"], "incomplete_or_provider_blocked")

    def test_parallel_and_hard_pack_gates_require_prior_signal(self) -> None:
        hold = build_parallel_subagent_gate_summary(
            equal_budget_summary={"decision": "no_measurable_isolation_gain"}
        )
        go = build_parallel_subagent_gate_summary(
            equal_budget_summary={"decision": "isolation_gain_candidate"}
        )
        readiness = build_hard_pack_subagent_readiness_summary(
            contract_summary={"artifact_complete": True},
            equal_budget_summary={"capability_conclusion_allowed": True},
            provider_stable=True,
        )
        self.assertFalse(hold["parallel_allowed"])
        self.assertTrue(go["parallel_allowed"])
        self.assertTrue(readiness["hard_pack_eval_allowed"])


if __name__ == "__main__":
    unittest.main()
