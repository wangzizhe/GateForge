from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.llm_provider_adapter import LLMProviderConfig, ToolCall, ToolResponse
from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import (
    WORKSPACE_TOOL_DEFS,
    _build_summary,
    _dispatch_workspace_tool,
    _safe_candidate_id,
    _timeout_result,
    run_workspace_style_case,
    run_workspace_style_probe,
)


class WorkspaceStyleProbeV067Tests(unittest.TestCase):
    def test_tool_count_is_six(self) -> None:
        self.assertEqual(len(WORKSPACE_TOOL_DEFS), 6)
        tool_names = {t["name"] for t in WORKSPACE_TOOL_DEFS}
        self.assertIn("batch_check_candidates", tool_names)

    def test_live_submit_checkpoint_is_not_exposed(self) -> None:
        self.assertNotIn("submit_checkpoint", inspect.signature(run_workspace_style_case).parameters)
        self.assertNotIn("submit_checkpoint", inspect.signature(run_workspace_style_probe).parameters)

    def test_safe_candidate_id_sanitizes_pathlike_text(self) -> None:
        self.assertEqual(_safe_candidate_id("../bad id"), ".._bad_id")

    def test_timeout_result_is_not_provider_error_or_auto_submit(self) -> None:
        result = _timeout_result({"case_id": "case_a", "model_name": "M"}, timeout_sec=7)
        self.assertEqual(result["final_verdict"], "FAILED_TIMEOUT")
        self.assertTrue(result["harness_timeout"])
        self.assertEqual(result["provider_error"], "")
        self.assertFalse(result["discipline"]["wrapper_auto_submit_added"])
        self.assertEqual(result["tool_count"], 6)

    def test_timeout_result_audits_existing_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workspace = root / "workspaces" / "case_a"
            workspace.mkdir(parents=True)
            (workspace / "candidate1.mo").write_text("model M\nend M;\n", encoding="utf-8")
            (workspace / "M.mo").write_text("model M\nend M;\n", encoding="utf-8")
            result = _timeout_result(
                {"case_id": "case_a", "model_name": "M"},
                timeout_sec=7,
                out_dir=root,
            )
        self.assertEqual(result["candidate_files"][0]["candidate_id"], "candidate1")
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
                        "dataset_split": "holdout",
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
                    "tool_count": 6,
                    "final_verdict": "PASS",
                    "submitted": True,
                    "submitted_candidate_id": "c1",
                    "step_count": 2,
                    "token_used": 1,
                    "provider_error": "",
                    "candidate_files": [{"candidate_id": "c1", "path": str(candidate), "write_check_ok": True}],
                    "steps": [],
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
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["tool_count"], 6)
        self.assertTrue(summary["discipline"]["transparent_workspace_enabled"])
        self.assertTrue(summary["discipline"]["merged_write_check_tool"])
        self.assertFalse(summary["discipline"]["wrapper_auto_submit_added"])
        self.assertEqual(summary["candidate_file_count"], 1)

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
        self.assertIn(
            "write_and_check",
            WORKSPACE_TOOL_DEFS[2]["name"],
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
        self.assertTrue(candidate_meta["c1"]["write_simulate_ok"])
        self.assertTrue(batch["batch_results"][0]["simulate_ok"])
        self.assertTrue(candidate_meta["c2"]["write_simulate_ok"])

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


if __name__ == "__main__":
    unittest.main()
