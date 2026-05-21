from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.llm_provider_adapter import LLMProviderConfig, ToolCall, ToolResponse
from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import (
    LONG_RUN_900S_PROFILE,
    RUN_PROFILES,
    WORKSPACE_TOOL_DEFS,
    _build_summary,
    _build_workspace_system_prompt,
    _dispatch_workspace_tool,
    _external_library_context_from_case,
    _redact_result_for_artifact,
    _safe_candidate_id,
    _timeout_result,
    run_workspace_style_case,
    run_workspace_style_probe,
)


class AgentModelicaWorkspaceStyleProbeV067Tests(unittest.TestCase):
    def test_tool_count_is_eight(self) -> None:
        self.assertEqual(len(WORKSPACE_TOOL_DEFS), 8)
        tool_names = {t["name"] for t in WORKSPACE_TOOL_DEFS}
        self.assertIn("search_workspace_files", tool_names)
        self.assertIn("read_file_slice", tool_names)
        self.assertIn("batch_check_candidates", tool_names)

    def test_live_submit_checkpoint_is_not_exposed(self) -> None:
        self.assertNotIn("submit_checkpoint", inspect.signature(run_workspace_style_case).parameters)
        self.assertNotIn("submit_checkpoint", inspect.signature(run_workspace_style_probe).parameters)

    def test_default_prompt_contains_no_repair_direction_hints(self) -> None:
        prompt = _build_workspace_system_prompt(preload_diagnostics=False)
        lowered = prompt.lower()
        banned = [
            "p.i = 0",
            "n.i = 0",
            "zero-flow",
            "positivepin",
            "negativepin",
            "ohm",
            "replace custom",
            "common modelica repair patterns",
            "fix those directly",
            "no exploration needed",
            "focus on remaining deficit",
            "combine effective changes",
            "equation balance summary",
            "structured diagnostics",
        ]

        for phrase in banned:
            self.assertNotIn(phrase, lowered)

    def test_workspace_tools_do_not_advertise_wrapper_diagnostics(self) -> None:
        text = json.dumps(WORKSPACE_TOOL_DEFS).lower()
        banned = [
            "equation balance summary",
            "structured diagnostics",
            "unconstrained variables",
            "flow sum equations",
            "subsystem imbalance",
        ]

        for phrase in banned:
            self.assertNotIn(phrase, text)

    def test_preloaded_diagnostic_prompt_is_observation_only(self) -> None:
        prompt = _build_workspace_system_prompt(preload_diagnostics=True)
        lowered = prompt.lower()

        self.assertIn("observations", lowered)
        self.assertIn("decide the repair plan yourself", lowered)
        self.assertNotIn("p.i = 0", lowered)
        self.assertNotIn("no exploration needed", lowered)

    def test_safe_candidate_id_sanitizes_pathlike_text(self) -> None:
        self.assertEqual(_safe_candidate_id("../bad id"), ".._bad_id")

    def test_read_file_rejects_directories_as_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = json.loads(_dispatch_workspace_tool(
                name="read_file",
                arguments={"path": "."},
                workspace=Path(td),
                candidate_paths={},
                candidate_meta={},
            ))

        self.assertEqual(result["error"], "path is not a file")

    def test_list_workspace_files_summarizes_external_library_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            (workspace / "initial.mo").write_text("model M\nend M;\n", encoding="utf-8")
            mirror = workspace / "Modelica"
            (mirror / "Blocks").mkdir(parents=True)
            (mirror / "package.mo").write_text("package Modelica\nend Modelica;\n", encoding="utf-8")
            (mirror / "Blocks" / "Continuous.mo").write_text("package Continuous\nend Continuous;\n", encoding="utf-8")

            result = json.loads(_dispatch_workspace_tool(
                name="list_workspace_files",
                arguments={},
                workspace=workspace,
                candidate_paths={},
                candidate_meta={},
            ))

        listed_paths = {row["path"] for row in result["files"]}
        self.assertIn("initial.mo", listed_paths)
        self.assertNotIn("Modelica/Blocks/Continuous.mo", listed_paths)
        self.assertIn(
            {"path": "Modelica/", "reason": "external_library_mirror", "type": "directory"},
            result["omitted"],
        )

    def test_read_file_truncates_large_files_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            large = "a" * 21_000 + "tail-marker"
            (workspace / "large.omc.txt").write_text(large, encoding="utf-8")
            result = json.loads(_dispatch_workspace_tool(
                name="read_file",
                arguments={"path": "large.omc.txt"},
                workspace=workspace,
                candidate_paths={},
                candidate_meta={},
            ))

        self.assertTrue(result["truncated"])
        self.assertEqual(result["path"], "large.omc.txt")
        self.assertLess(len(json.dumps(result)), 20_000)
        self.assertTrue(result["tail"].endswith("tail-marker"))

    def test_search_and_read_file_slice_support_large_file_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            model = workspace / "Modelica" / "Blocks" / "Example.mo"
            model.parent.mkdir(parents=True)
            model.write_text(
                "model Example\n"
                "  Real x;\n"
                "  Real targetSignal;\n"
                "equation\n"
                "  targetSignal = x;\n"
                "end Example;\n",
                encoding="utf-8",
            )
            search = json.loads(_dispatch_workspace_tool(
                name="search_workspace_files",
                arguments={"pattern": "targetSignal", "glob": "**/*.mo"},
                workspace=workspace,
                candidate_paths={},
                candidate_meta={},
            ))
            slice_result = json.loads(_dispatch_workspace_tool(
                name="read_file_slice",
                arguments={"path": "Modelica/Blocks/Example.mo", "start_line": 3, "line_count": 2},
                workspace=workspace,
                candidate_paths={},
                candidate_meta={},
            ))

        self.assertEqual(search["match_count"], 2)
        self.assertEqual(search["matches"][0]["path"], "Modelica/Blocks/Example.mo")
        self.assertEqual(slice_result["start_line"], 3)
        self.assertIn("targetSignal", slice_result["content"])
        self.assertNotIn("diagnostics", search)
        self.assertNotIn("equation_balance", slice_result)

    def test_search_workspace_files_rejects_absolute_globs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = json.loads(_dispatch_workspace_tool(
                name="search_workspace_files",
                arguments={"pattern": "x", "glob": "/tmp/**/*.mo"},
                workspace=Path(td),
                candidate_paths={},
                candidate_meta={},
            ))

        self.assertEqual(result["error"], "glob must be workspace-relative")

    def test_artifact_redaction_handles_batch_candidate_model_text(self) -> None:
        result = _redact_result_for_artifact(
            {
                "steps": [
                    {
                        "tool_calls": [
                            {
                                "name": "batch_check_candidates",
                                "arguments": {
                                    "candidates": [
                                        {
                                            "candidate_id": "c2",
                                            "model_text": "model M\n  Real x;\nend M;",
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        )

        model_text = result["steps"][0]["tool_calls"][0]["arguments"]["candidates"][0]["model_text"]
        self.assertIsInstance(model_text, dict)
        self.assertEqual(model_text["candidate_id"], "c2")
        self.assertEqual(model_text["char_count"], len("model M\n  Real x;\nend M;"))
        self.assertNotIn("Real x", json.dumps(result))

    def test_artifact_redaction_is_idempotent(self) -> None:
        first = _redact_result_for_artifact(
            {
                "steps": [
                    {
                        "tool_calls": [
                            {
                                "name": "write_and_check_candidate_model",
                                "arguments": {
                                    "candidate_id": "c1",
                                    "model_text": "model M\n  Real x;\nend M;",
                                },
                            }
                        ]
                    }
                ]
            }
        )
        second = _redact_result_for_artifact(first)

        self.assertEqual(first, second)

    def test_timeout_result_is_not_provider_error_or_auto_submit(self) -> None:
        result = _timeout_result({"case_id": "case_a", "model_name": "M"}, timeout_sec=7)
        self.assertEqual(result["final_verdict"], "FAILED_TIMEOUT")
        self.assertTrue(result["harness_timeout"])
        self.assertEqual(result["provider_error"], "")
        self.assertFalse(result["discipline"]["wrapper_auto_submit_added"])
        self.assertEqual(result["tool_count"], 8)

    def test_timeout_result_audits_existing_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "case_a"
            workspace.mkdir(parents=True)
            (workspace / "case_status.json").write_text(
                json.dumps({"step": 2, "token_used": 65, "timeout_phase": "provider_request"}),
                encoding="utf-8",
            )
            (workspace / "candidate1.mo").write_text("model M\nend M;\n", encoding="utf-8")
            (workspace / "candidate1.omc.txt").write_text(
                'Check of M completed successfully.\nrecord SimulationResult resultFile = "M_res.mat"\n',
                encoding="utf-8",
            )
            (workspace / "P.System.mo").write_text("within P;\nmodel System\nend System;\n", encoding="utf-8")
            result = _timeout_result(
                {"case_id": "case_a", "model_name": "P.System"},
                timeout_sec=7,
                out_dir=root,
                max_token_budget=64,
            )
        self.assertEqual(result["candidate_files"][0]["candidate_id"], "candidate1")
        self.assertEqual(result["step_count"], 2)
        self.assertEqual(result["token_used"], 65)
        self.assertEqual(result["max_token_budget"], 64)
        self.assertTrue(result["token_budget_exceeded"])
        self.assertTrue(result["candidate_files"][0]["write_check_ok"])
        self.assertTrue(result["candidate_files"][0]["write_simulate_ok"])
        self.assertEqual(result["passing_candidate_ids"], ["candidate1"])
        self.assertEqual(result["passing_candidate_count"], 1)
        self.assertEqual(len(result["candidate_files"]), 1)

    def test_run_workspace_style_probe_writes_streaming_outputs_with_mock_case(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = root / "tasks.jsonl"
            out_dir = root / "out"
            tasks.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "description": "Fix model",
                        "initial_model": "model M\n Real x;\nend M;\n",
                        "verification": {"simulate": {"stop_time": 0.1, "intervals": 10}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_run_case(case, *, out_dir, max_steps, max_token_budget, planner_backend):
                workspace = out_dir / "workspaces" / case["case_id"]
                workspace.mkdir(parents=True, exist_ok=True)
                candidate = workspace / "c1.mo"
                candidate.write_text(
                    "model M\n  Real x;\nequation\n  x = 1;\nend M;\n", encoding="utf-8"
                )
                return {
                    "case_id": case["case_id"],
                    "model_name": case["model_name"],
                    "provider": "mock",
                    "run_mode": "workspace_style_tool_use",
                    "tool_count": 8,
                    "final_verdict": "PASS",
                    "submitted": True,
                    "submitted_candidate_id": "c1",
                    "step_count": 2,
                    "token_used": 1,
                    "provider_error": "",
                    "candidate_files": [{"candidate_id": "c1", "path": str(candidate), "write_check_ok": True}],
                    "steps": [
                        {
                            "step": 1,
                            "tool_calls": [
                                {
                                    "name": "write_and_check_candidate_model",
                                    "arguments": {
                                        "candidate_id": "c1",
                                        "model_text": candidate.read_text(encoding="utf-8"),
                                    },
                                }
                            ],
                        }
                    ],
                    "final_model_text": candidate.read_text(encoding="utf-8"),
                    "discipline": {
                        "deterministic_repair_added": False,
                        "hidden_routing_added": False,
                        "candidate_selection_added": False,
                        "wrapper_auto_submit_added": False,
                    },
                }

            summary = run_workspace_style_probe(
                tasks_path=tasks,
                out_dir=out_dir,
                run_case_fn=fake_run_case,
            )
            result_row = json.loads((out_dir / "results.jsonl").read_text(encoding="utf-8").strip())
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["tool_count"], 8)
        self.assertTrue(summary["discipline"]["transparent_workspace_enabled"])
        self.assertTrue(summary["discipline"]["merged_write_check_tool"])
        self.assertFalse(summary["discipline"]["wrapper_auto_submit_added"])
        self.assertEqual(summary["candidate_file_count"], 1)
        self.assertEqual(summary["run_profile"], "custom")
        self.assertEqual(summary["max_steps"], 10)
        self.assertEqual(summary["per_case_timeout_sec"], 0)
        recorded_model_text = result_row["steps"][0]["tool_calls"][0]["arguments"]["model_text"]
        self.assertIsInstance(recorded_model_text, dict)
        self.assertEqual(recorded_model_text["candidate_id"], "c1")
        self.assertEqual(recorded_model_text["char_count"], len(result_row["final_model_text"]))
        self.assertNotIn("Real x", json.dumps(result_row["steps"][0]["tool_calls"][0]["arguments"]))

    def test_summary_records_run_profile_metadata(self) -> None:
        profile = RUN_PROFILES[LONG_RUN_900S_PROFILE]
        summary = _build_summary(
            tasks=[{"case_id": "case_a"}],
            results=[
                {
                    "case_id": "case_a",
                    "final_verdict": "PASS",
                    "provider_error": "",
                    "harness_timeout": False,
                    "runner_error": "",
                    "submission_mode": "llm",
                    "candidate_files": [],
                }
            ],
            run_profile=LONG_RUN_900S_PROFILE,
            max_steps=profile["max_steps"],
            max_token_budget=profile["max_token_budget"],
            per_case_timeout_sec=profile["per_case_timeout_sec"],
        )

        self.assertEqual(summary["run_profile"], LONG_RUN_900S_PROFILE)
        self.assertEqual(summary["max_steps"], 100)
        self.assertEqual(summary["per_case_timeout_sec"], 900)
        self.assertEqual(summary["max_token_budget"], 999999999)

    def test_summary_blocks_checkpoint_contaminated_results(self) -> None:
        summary = _build_summary(
            tasks=[{"case_id": "case_a"}],
            results=[
                {
                    "case_id": "case_a",
                    "final_verdict": "PASS",
                    "provider_error": "",
                    "harness_timeout": False,
                    "runner_error": "",
                    "submit_checkpoint_triggered": True,
                    "submission_mode": "checkpoint",
                    "candidate_files": [],
                }
            ],
        )
        self.assertFalse(summary["conclusion_allowed"])
        self.assertEqual(summary["submit_checkpoint_count"], 1)
        self.assertEqual(summary["llm_submitted_pass_count"], 0)
        self.assertEqual(summary["non_llm_submitted_pass_count"], 1)
        self.assertTrue(summary["discipline"]["llm_submit_required"])

    def test_summary_reports_merged_write_check_flag(self) -> None:
        self.assertTrue(
            any("write_and_check" in tool["name"] for tool in WORKSPACE_TOOL_DEFS),
            "tool list must contain write_and_check_tool",
        )

    def test_summary_reports_invalid_submission_attempts(self) -> None:
        summary = _build_summary(
            tasks=[{"case_id": "case_a"}],
            results=[
                {
                    "case_id": "case_a",
                    "final_verdict": "FAILED",
                    "provider_error": "",
                    "harness_timeout": False,
                    "runner_error": "",
                    "invalid_submission_attempt_count": 2,
                    "candidate_files": [],
                }
            ],
        )
        self.assertEqual(summary["invalid_submission_attempt_count"], 2)
        self.assertTrue(summary["conclusion_allowed"])

    def test_summary_records_over_token_budget_results_without_blocking_conclusion(self) -> None:
        summary = _build_summary(
            tasks=[{"case_id": "case_a"}],
            results=[
                {
                    "case_id": "case_a",
                    "final_verdict": "PASS",
                    "provider_error": "",
                    "harness_timeout": False,
                    "runner_error": "",
                    "submission_mode": "llm",
                    "candidate_files": [],
                    "token_used": 65,
                }
            ],
            max_token_budget=64,
        )

        self.assertTrue(summary["conclusion_allowed"])
        self.assertEqual(summary["over_token_budget_count"], 1)
        self.assertEqual(summary["over_token_budget_case_ids"], ["case_a"])
        self.assertEqual(summary["over_token_budget_rows"][0]["token_used"], 65)
        self.assertEqual(summary["over_token_budget_rows"][0]["token_overage"], 1)

    def test_write_and_batch_candidates_record_simulation_status_and_omc_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            candidate_paths = {}
            candidate_meta = {}
            omc_output = (
                "Class M has 1 equation(s) and 1 variable(s).\n"
                "The simulation finished successfully.\n"
            )
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=(omc_output, True, True),
            ):
                single = json.loads(_dispatch_workspace_tool(
                    name="write_and_check_candidate_model",
                    arguments={"candidate_id": "c1", "model_text": "model M\nequation\nend M;"},
                    workspace=workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                ))
                batch = json.loads(_dispatch_workspace_tool(
                    name="batch_check_candidates",
                    arguments={
                        "candidates": [
                            {"candidate_id": "c2", "model_text": "model M\nequation\nend M;"}
                        ]
                    },
                    workspace=workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                ))
            self.assertTrue(Path(single["omc_output_path"]).exists())

        self.assertTrue(single["check_ok"])
        self.assertTrue(single["simulate_ok"])
        self.assertNotIn("equation_balance", single)
        self.assertNotIn("diagnostics", single)
        self.assertTrue(candidate_meta["c1"]["write_simulate_ok"])
        self.assertTrue(batch["batch_results"][0]["simulate_ok"])
        self.assertNotIn("deficit", batch["batch_results"][0])
        self.assertNotIn("balance", batch["batch_results"][0])
        self.assertTrue(candidate_meta["c2"]["write_simulate_ok"])

    def test_candidate_warning_pass_uses_final_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            candidate_paths = {}
            candidate_meta = {}
            warning_output = (
                "Check of M completed successfully.\n"
                "Class M has 1 equation(s) and 1 variable(s).\n"
                "record SimulationResult\n"
                '    resultFile = "/workspace/M_res.mat",\n'
                '    messages = "LOG_ASSERT | warning | assertion failed during initialization: Invalid root\\n'
                'LOG_SUCCESS | info | The simulation finished successfully."\n'
                "end SimulationResult;\n"
            )
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=(warning_output, True, False),
            ):
                single = json.loads(_dispatch_workspace_tool(
                    name="write_and_check_candidate_model",
                    arguments={"candidate_id": "c1", "model_text": "model M\nequation\nend M;"},
                    workspace=workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                ))

        self.assertTrue(single["check_ok"])
        self.assertTrue(single["simulate_ok"])
        self.assertTrue(single["policy_pass"])
        self.assertFalse(single["strict_simulate_ok"])
        self.assertEqual(single["simulation_status"], "warning_pass")
        self.assertFalse(single["raw_simulate_ok"])
        self.assertTrue(candidate_meta["c1"]["write_simulate_ok"])
        self.assertTrue(candidate_meta["c1"]["write_policy_pass"])
        self.assertEqual(candidate_meta["c1"]["write_simulation_status"], "warning_pass")

    def test_submit_if_passes_accepts_warning_pass_policy(self) -> None:
        class FakeAdapter:
            def send_tool_request(self, messages, tools, config):
                return (
                    ToolResponse(
                        text="write warning-pass candidate",
                        tool_calls=[
                            ToolCall(
                                id="call_1",
                                name="write_and_check_candidate_model",
                                arguments={
                                    "candidate_id": "c1",
                                    "model_text": "model M\nend M;",
                                    "submit_if_passes": True,
                                },
                            )
                        ],
                        finish_reason="tool_calls",
                        usage={"total_tokens": 1},
                    ),
                    "",
                )

        warning_output = (
            "Check of M completed successfully.\n"
            "Class M has 1 equation(s) and 1 variable(s).\n"
            "record SimulationResult\n"
            '    resultFile = "/workspace/M_res.mat",\n'
            '    messages = "LOG_ASSERT | warning | assertion failed during initialization: Invalid root\\n'
            'LOG_SUCCESS | info | The simulation finished successfully."\n'
            "end SimulationResult;\n"
        )
        case = {
            "case_id": "case_a",
            "model_name": "M",
            "model_text": "model M\nend M;\n",
            "workflow_goal": "Fix model",
        }
        config = LLMProviderConfig(provider_name="mock", model="mock", api_key="mock")
        with tempfile.TemporaryDirectory() as td:
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0.resolve_provider_adapter",
                return_value=(FakeAdapter(), config),
            ), patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=(warning_output, True, False),
            ), patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_simulate",
                return_value=(warning_output, True, False),
            ):
                result = run_workspace_style_case(case, out_dir=Path(td), max_steps=1)

        self.assertTrue(result["submitted"])
        self.assertEqual(result["submitted_candidate_id"], "c1")
        self.assertEqual(result["submission_mode"], "llm_submit_if_passes")
        self.assertEqual(result["final_verdict"], "PASS")
        self.assertEqual(result["final_simulation_status"], "warning_pass")
        self.assertFalse(result["final_strict_simulate_ok"])

    def test_runner_does_not_inject_compaction_guidance(self) -> None:
        class FakeAdapter:
            def __init__(self) -> None:
                self.messages_seen: list[list[dict]] = []

            def send_tool_request(self, messages, tools, config):
                self.messages_seen.append(list(messages))
                return (
                    ToolResponse(
                        text="continue",
                        tool_calls=[],
                        finish_reason="stop",
                        usage={"total_tokens": 10},
                    ),
                    "",
                )

        adapter = FakeAdapter()
        case = {
            "case_id": "case_a",
            "model_name": "M",
            "model_text": "model M\nend M;\n",
            "workflow_goal": "Fix model",
        }
        config = LLMProviderConfig(provider_name="mock", model="mock", api_key="mock")
        with tempfile.TemporaryDirectory() as td:
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0.resolve_provider_adapter",
                return_value=(adapter, config),
            ):
                run_workspace_style_case(case, out_dir=Path(td), max_steps=4, max_token_budget=20)

        visible_text = "\n".join(
            str(message.get("content") or "")
            for batch in adapter.messages_seen
            for message in batch
        ).lower()
        self.assertNotIn("session summary", visible_text)
        self.assertNotIn("focus on remaining deficit", visible_text)
        self.assertNotIn("combine effective changes", visible_text)

    def test_case_workspace_is_cleaned_before_run(self) -> None:
        class FakeAdapter:
            def send_tool_request(self, messages, tools, config):
                return (
                    ToolResponse(
                        text="done",
                        tool_calls=[],
                        finish_reason="stop",
                        usage={"total_tokens": 10},
                    ),
                    "",
                )

        case = {
            "case_id": "case_a",
            "model_name": "M",
            "model_text": "model M\nend M;\n",
            "workflow_goal": "Fix model",
        }
        config = LLMProviderConfig(provider_name="mock", model="mock", api_key="mock")
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            stale = out_dir / "workspaces" / "case_a" / "Modelica" / "package.mo"
            stale.parent.mkdir(parents=True)
            stale.write_text("package Modelica\nend Modelica;\n", encoding="utf-8")
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0.resolve_provider_adapter",
                return_value=(FakeAdapter(), config),
            ):
                run_workspace_style_case(case, out_dir=out_dir, max_steps=1, max_token_budget=20)

            self.assertFalse(stale.exists())
            self.assertTrue((out_dir / "workspaces" / "case_a" / "initial.mo").exists())

    def test_candidate_checks_use_explicit_target_model_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            candidate_paths = {}
            candidate_meta = {}
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=("Class P.System has 1 equation(s) and 1 variable(s).", True, True),
            ) as mock_check:
                _dispatch_workspace_tool(
                    name="write_and_check_candidate_model",
                    arguments={
                        "candidate_id": "c1",
                        "model_text": "within P;\nmodel Adapter\nend Adapter;\nwithin P;\nmodel System\nend System;",
                    },
                    workspace=workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                    target_model_name="P.System",
                )

        self.assertEqual(mock_check.call_args.kwargs["target_model_name"], "P.System")
        self.assertEqual(candidate_meta["c1"]["model_name"], "P.System")

    def test_external_library_context_is_read_from_task_payload(self) -> None:
        context = _external_library_context_from_case(
            {
                "task_payload": {
                    "source_library_path": "/repo/ExternalLib",
                    "source_package_name": "ExternalLib",
                    "source_library_model_path": "/repo/ExternalLib/A/B.mo",
                    "source_qualified_model_name": "ExternalLib.A.B",
                }
            }
        )

        self.assertEqual(context["source_package_name"], "ExternalLib")
        self.assertEqual(context["source_qualified_model_name"], "ExternalLib.A.B")

    def test_candidate_checks_receive_external_library_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            candidate_paths = {}
            candidate_meta = {}
            library_context = {
                "source_library_path": "/repo/ExternalLib",
                "source_package_name": "ExternalLib",
                "source_library_model_path": "/repo/ExternalLib/A/B.mo",
                "source_qualified_model_name": "ExternalLib.A.B",
            }
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=("Class ExternalLib.A.B has 1 equation(s) and 1 variable(s).", True, True),
            ) as mock_check:
                _dispatch_workspace_tool(
                    name="write_and_check_candidate_model",
                    arguments={"candidate_id": "c1", "model_text": "within ExternalLib.A;\nmodel B\nend B;"},
                    workspace=workspace,
                    candidate_paths=candidate_paths,
                    candidate_meta=candidate_meta,
                    target_model_name="ExternalLib.A.B",
                    external_library_context=library_context,
                )

        self.assertEqual(mock_check.call_args.kwargs["external_library_context"], library_context)

    def test_invalid_submit_candidate_does_not_count_as_submission(self) -> None:
        class FakeAdapter:
            def send_tool_request(self, messages, tools, config):
                return (
                    ToolResponse(
                        text="submit missing candidate",
                        tool_calls=[
                            ToolCall(
                                id="call_1",
                                name="submit_candidate_model",
                                arguments={"candidate_id": "missing"},
                            )
                        ],
                        finish_reason="tool_calls",
                        usage={"total_tokens": 1},
                    ),
                    "",
                )

        case = {
            "case_id": "case_a",
            "model_name": "M",
            "model_text": "model M\nend M;\n",
            "workflow_goal": "Fix model",
        }
        config = LLMProviderConfig(provider_name="mock", model="mock", api_key="mock")
        with tempfile.TemporaryDirectory() as td:
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0.resolve_provider_adapter",
                return_value=(FakeAdapter(), config),
            ):
                result = run_workspace_style_case(case, out_dir=Path(td), max_steps=1)

        self.assertFalse(result["submitted"])
        self.assertEqual(result["submission_mode"], "none")
        self.assertEqual(result["invalid_submission_attempt_count"], 1)
        self.assertEqual(result["submitted_candidate_id"], "")
        self.assertEqual(result["final_verdict"], "FAILED")

    def test_final_submission_uses_omc_parser_flags(self) -> None:
        class FakeAdapter:
            def send_tool_request(self, messages, tools, config):
                if len([m for m in messages if m.get("role") == "tool"]) == 0:
                    return (
                        ToolResponse(
                            text="write candidate",
                            tool_calls=[
                                ToolCall(
                                    id="call_1",
                                    name="write_and_check_candidate_model",
                                    arguments={"candidate_id": "c1", "model_text": "model M\nend M;"},
                                )
                            ],
                            finish_reason="tool_calls",
                            usage={"total_tokens": 1},
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
                                arguments={"candidate_id": "c1"},
                            )
                        ],
                        finish_reason="tool_calls",
                        usage={"total_tokens": 1},
                    ),
                    "",
                )

        case = {
            "case_id": "case_a",
            "model_name": "M",
            "model_text": "model M\nend M;\n",
            "workflow_goal": "Fix model",
        }
        config = LLMProviderConfig(provider_name="mock", model="mock", api_key="mock")
        with tempfile.TemporaryDirectory() as td:
            with patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0.resolve_provider_adapter",
                return_value=(FakeAdapter(), config),
            ), patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_check",
                return_value=("record SimulationResult\nThe simulation finished successfully.", True, True),
            ), patch(
                "gateforge.agent_modelica_workspace_style_probe_v0_67_0._run_omc_simulate",
                return_value=("record SimulationResult\nThe simulation finished successfully.", False, True),
            ):
                result = run_workspace_style_case(case, out_dir=Path(td), max_steps=2)

        self.assertTrue(result["submitted"])
        self.assertEqual(result["final_verdict"], "FAILED")
        final_eval = [step for step in result["steps"] if step.get("step") == "final_eval"][0]
        self.assertFalse(final_eval["check_ok"])


if __name__ == "__main__":
    unittest.main()
