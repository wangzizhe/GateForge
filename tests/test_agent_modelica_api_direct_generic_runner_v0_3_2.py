from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_api_direct_generic_runner_v0_3_2 import (
    APIDirectToolCall,
    APIDirectTurnResult,
    AnthropicMessagesToolClient,
    build_api_direct_task_prompt,
    build_anthropic_tools,
    build_openai_function_tools,
    run_api_direct_generic_runner,
    run_api_direct_task,
)
from gateforge.llm_provider_adapter import LLMProviderConfig


class _FakeClient:
    def __init__(self, turns: list[APIDirectTurnResult]) -> None:
        self.turns = list(turns)
        self.calls: list[dict] = []

    def run_turn(self, *, input_items, tools, model_id, final_schema):
        self.calls.append(
            {
                "input_items": list(input_items),
                "tools": list(tools),
                "model_id": str(model_id),
                "final_schema": dict(final_schema),
            }
        )
        if not self.turns:
            raise AssertionError("unexpected_turn")
        return self.turns.pop(0)


class _FakeToolExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
        args = dict(arguments or {})
        self.calls.append((str(tool_name), args))
        return {"ok": True, "artifact_path": "/tmp/check.txt", "error_message": ""}


class AgentModelicaApiDirectGenericRunnerV032Tests(unittest.TestCase):
    def test_build_openai_function_tools_covers_shared_omc_surface(self) -> None:
        tools = build_openai_function_tools()
        tool_names = {row["name"] for row in tools}
        self.assertEqual(
            tool_names,
            {"omc_check_model", "omc_simulate_model", "omc_get_error_string", "omc_read_artifact"},
        )
        self.assertTrue(all(row["type"] == "function" for row in tools))

    def test_build_anthropic_tools_covers_shared_omc_surface(self) -> None:
        tools = build_anthropic_tools()
        tool_names = {row["name"] for row in tools}
        self.assertEqual(
            tool_names,
            {"omc_check_model", "omc_simulate_model", "omc_get_error_string", "omc_read_artifact"},
        )
        self.assertTrue(all("input_schema" in row for row in tools))

    def test_build_api_direct_task_prompt_includes_fairness_checklist_and_tools(self) -> None:
        prompt = build_api_direct_task_prompt(
            task_ctx={
                "task_id": "t1",
                "failure_type": "runtime_fail",
                "expected_stage": "simulate",
                "model_name": "M",
                "source_package_name": "Buildings",
                "extra_model_loads": ["Buildings"],
                "model_text": "model M end M;",
            },
            budget={"max_agent_rounds": 3, "max_omc_tool_calls": 4, "max_wall_clock_sec": 90},
            tool_defs=build_openai_function_tools(),
        )
        self.assertIn("Fairness checklist", prompt)
        self.assertIn("available_omc_tools", prompt)
        self.assertIn("multi-round tool use is allowed", prompt)
        self.assertIn("model M end M;", prompt)

    def test_run_api_direct_task_executes_tool_then_verifies(self) -> None:
        client = _FakeClient(
            [
                APIDirectTurnResult(
                    output_items=[
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "omc_check_model",
                            "arguments": "{\"model_text\":\"model M end M;\",\"model_name\":\"M\"}",
                        }
                    ],
                    tool_calls=[
                        APIDirectToolCall(
                            call_id="call_1",
                            name="omc_check_model",
                            arguments={"model_text": "model M end M;", "model_name": "M"},
                        )
                    ],
                    output_text="",
                ),
                APIDirectTurnResult(
                    output_items=[],
                    tool_calls=[],
                    output_text=json.dumps(
                        {
                            "task_status": "FAIL",
                            "budget_exhausted": False,
                            "rounds_used_estimate": 2,
                            "patched_model_text": "model M end M;",
                            "repair_rationale": "checked",
                        }
                    ),
                ),
            ]
        )
        executor = _FakeToolExecutor()
        with mock.patch(
            "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2._verify_candidate",
            return_value={"ok": True, "artifact_path": "/tmp/verify.txt"},
        ):
            record = run_api_direct_task(
                task_ctx={
                    "task_id": "t1",
                    "failure_type": "runtime_fail",
                    "expected_stage": "simulate",
                    "model_name": "M",
                    "source_file_name": "M.mo",
                    "source_library_path": "",
                    "source_package_name": "",
                    "source_library_model_path": "",
                    "source_qualified_model_name": "M",
                    "extra_model_loads": [],
                    "model_text": "model M end M;",
                },
                budget={"max_agent_rounds": 3, "max_omc_tool_calls": 4, "max_wall_clock_sec": 90},
                client=client,
                tool_executor=executor,
                tool_defs=build_openai_function_tools(),
                model_id="gpt-5",
                docker_image="openmodelica/openmodelica:test",
                artifact_root="/tmp/api_direct_task",
            )
        self.assertTrue(record["success"])
        self.assertEqual(record["task_status"], "PASS")
        self.assertEqual(record["omc_tool_call_count"], 1)
        self.assertEqual(executor.calls[0][0], "omc_check_model")
        self.assertEqual(client.calls[0]["model_id"], "gpt-5")

    def test_run_api_direct_generic_runner_writes_normalized_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_api_direct_runner_") as td:
            root = Path(td)
            mutant = root / "mutant.mo"
            mutant.write_text("model M end M;", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "failure_type": "runtime_fail",
                                "expected_stage": "simulate",
                                "mutated_model_path": str(mutant),
                                "source_meta": {"qualified_model_name": "M"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            budget = root / "budget.json"
            budget.write_text(
                json.dumps(
                    {
                        "track_c_budget_authority": {
                            "recommended_budget": {
                                "max_agent_rounds": 3,
                                "max_omc_tool_calls": 4,
                                "max_wall_clock_sec": 90,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            fake_client = _FakeClient(
                [
                    APIDirectTurnResult(
                        output_items=[
                            {
                                "type": "function_call",
                                "call_id": "call_1",
                                "name": "omc_check_model",
                                "arguments": "{\"model_text\":\"model M end M;\",\"model_name\":\"M\"}",
                            }
                        ],
                        tool_calls=[
                            APIDirectToolCall(
                                call_id="call_1",
                                name="omc_check_model",
                                arguments={"model_text": "model M end M;", "model_name": "M"},
                            )
                        ],
                        output_text="",
                    ),
                    APIDirectTurnResult(
                        output_items=[],
                        tool_calls=[],
                        output_text=json.dumps(
                            {
                                "task_status": "FAIL",
                                "budget_exhausted": False,
                                "rounds_used_estimate": 2,
                                "patched_model_text": "model M end M;",
                                "repair_rationale": "checked",
                            }
                        ),
                    ),
                ]
            )

            with mock.patch(
                "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2._build_client",
                return_value=(fake_client, "openai", "gpt-5"),
            ), mock.patch(
                "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2.OmcMcpServer"
            ) as server_cls, mock.patch(
                "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2._verify_candidate",
                return_value={"ok": True, "artifact_path": "/tmp/verify.txt"},
            ):
                server_cls.return_value.call_tool.return_value = {"ok": True, "artifact_path": "/tmp/check.txt"}
                summary = run_api_direct_generic_runner(
                    provider_family="openai",
                    arm_id="arm_api_direct_generic",
                    taskset_path=str(taskset),
                    out_dir=str(root / "out"),
                    budget_path=str(budget),
                    model_id="gpt-5",
                    docker_image="openmodelica/openmodelica:test",
                )
            self.assertEqual(summary["status"], "PASS")
            normalized = json.loads((root / "out" / "normalized_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized["provider_name"], "openai_api_direct")
            self.assertEqual(normalized["summary"]["success_count"], 1)

    def test_anthropic_client_parses_tool_use_blocks(self) -> None:
        client = AnthropicMessagesToolClient(
            config=LLMProviderConfig(provider_name="anthropic", model="claude-test", api_key="key")
        )
        with mock.patch.object(
            client,
            "_post",
            return_value={
                "id": "msg_1",
                "content": [
                    {"type": "text", "text": "checking"},
                    {"type": "tool_use", "id": "toolu_1", "name": "omc_check_model", "input": {"model_name": "M"}},
                ],
            },
        ) as post_mock:
            turn = client.run_turn(
                input_items=["repair this model"],
                tools=build_anthropic_tools(),
                model_id="claude-test",
                final_schema={"type": "object", "properties": {}},
            )
        self.assertEqual(turn.response_id, "msg_1")
        self.assertEqual(turn.tool_calls[0].name, "omc_check_model")
        self.assertEqual(turn.tool_calls[0].arguments["model_name"], "M")
        self.assertIn("checking", turn.output_text)
        payload = post_mock.call_args.args[0]
        self.assertEqual(payload["model"], "claude-test")
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_run_api_direct_generic_runner_supports_anthropic_provider_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_api_direct_runner_anthropic_") as td:
            root = Path(td)
            mutant = root / "mutant.mo"
            mutant.write_text("model M end M;", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "failure_type": "runtime_fail",
                                "expected_stage": "simulate",
                                "mutated_model_path": str(mutant),
                                "source_meta": {"qualified_model_name": "M"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            budget = root / "budget.json"
            budget.write_text(
                json.dumps(
                    {
                        "track_c_budget_authority": {
                            "recommended_budget": {
                                "max_agent_rounds": 3,
                                "max_omc_tool_calls": 4,
                                "max_wall_clock_sec": 90,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            fake_client = _FakeClient(
                [
                    APIDirectTurnResult(
                        output_items=[{"type": "tool_use", "id": "toolu_1", "name": "omc_check_model", "input": {"model_name": "M"}}],
                        tool_calls=[APIDirectToolCall(call_id="toolu_1", name="omc_check_model", arguments={"model_name": "M"})],
                        output_text="",
                    ),
                    APIDirectTurnResult(
                        output_items=[{"type": "text", "text": json.dumps({"task_status": "FAIL", "budget_exhausted": False, "rounds_used_estimate": 2, "patched_model_text": "model M end M;", "repair_rationale": "checked"})}],
                        tool_calls=[],
                        output_text=json.dumps(
                            {
                                "task_status": "FAIL",
                                "budget_exhausted": False,
                                "rounds_used_estimate": 2,
                                "patched_model_text": "model M end M;",
                                "repair_rationale": "checked",
                            }
                        ),
                    ),
                ]
            )
            with mock.patch(
                "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2._build_client",
                return_value=(fake_client, "anthropic", "claude-sonnet-test"),
            ), mock.patch(
                "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2.OmcMcpServer"
            ) as server_cls, mock.patch(
                "gateforge.agent_modelica_api_direct_generic_runner_v0_3_2._verify_candidate",
                return_value={"ok": True, "artifact_path": "/tmp/verify.txt"},
            ):
                server_cls.return_value.call_tool.return_value = {"ok": True, "artifact_path": "/tmp/check.txt"}
                summary = run_api_direct_generic_runner(
                    provider_family="anthropic",
                    arm_id="arm_api_direct_generic_claude",
                    taskset_path=str(taskset),
                    out_dir=str(root / "out"),
                    budget_path=str(budget),
                    model_id="claude-sonnet-test",
                    docker_image="openmodelica/openmodelica:test",
                )
            self.assertEqual(summary["provider_name"], "anthropic_api_direct")
            normalized = json.loads((root / "out" / "normalized_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized["provider_name"], "anthropic_api_direct")


if __name__ == "__main__":
    unittest.main()
