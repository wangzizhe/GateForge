from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_external_agent_live_runner_v0_3_1 import (
    _arm_prompt,
    _extract_json_payload,
    run_external_agent_live,
)


class AgentModelicaExternalAgentLiveRunnerV031Tests(unittest.TestCase):
    def test_extract_json_payload_handles_wrapped_text(self) -> None:
        payload = _extract_json_payload("noise\n{\"task_status\":\"FAIL\",\"budget_exhausted\":false,\"rounds_used_estimate\":1,\"patched_model_text\":\"model M end M;\",\"repair_rationale\":\"x\"}\ntrailer")
        self.assertEqual(payload["task_status"], "FAIL")

    def test_arm_prompt_mentions_mcp_and_budget(self) -> None:
        prompt = _arm_prompt(
            {
                "task_id": "t1",
                "failure_type": "runtime",
                "expected_stage": "simulate",
                "model_name": "M",
                "source_library_path": "/tmp/Buildings",
                "source_package_name": "Buildings",
                "source_library_model_path": "/tmp/Buildings/Electrical/ACSimpleGrid.mo",
                "source_qualified_model_name": "Buildings.Electrical.Examples.M",
                "extra_model_loads": ["Buildings"],
                "model_text": "model M end M;",
            },
            arm_id="arm2_frozen_structured_prompt",
            budget={"max_agent_rounds": 3, "max_omc_tool_calls": 6, "max_wall_clock_sec": 90},
        )
        self.assertIn("OpenModelica MCP tools", prompt)
        self.assertIn("max_omc_tool_calls: 6", prompt)
        self.assertIn("Work in short iterations", prompt)
        self.assertIn("source_library_path: /tmp/Buildings", prompt)
        self.assertIn("source_library_model_path: /tmp/Buildings/Electrical/ACSimpleGrid.mo", prompt)
        self.assertIn("source_qualified_model_name: Buildings.Electrical.Examples.M", prompt)
        self.assertIn("Library-context fields to preserve on every OMC tool call", prompt)

    def test_run_external_agent_live_normalizes_inline_mcp_provider_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_external_live_") as td:
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
                                "max_omc_tool_calls": 6,
                                "max_wall_clock_sec": 90,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            def _fake_run(cmd, *, timeout_sec):
                if cmd[0] == "claude":
                    return mock.Mock(
                        returncode=0,
                        stdout=json.dumps(
                            {
                                "task_status": "FAIL",
                                "budget_exhausted": False,
                                "rounds_used_estimate": 2,
                                "patched_model_text": "model M end M;",
                                "repair_rationale": "no-op",
                            }
                        ),
                        stderr="",
                    )
                raise AssertionError(cmd)

            with mock.patch(
                "gateforge.agent_modelica_external_agent_live_runner_v0_3_1._run_subprocess",
                side_effect=_fake_run,
            ), mock.patch(
                "gateforge.agent_modelica_external_agent_live_runner_v0_3_1._tool_call_count",
                return_value=2,
            ), mock.patch(
                "gateforge.agent_modelica_external_agent_live_runner_v0_3_1._verify_candidate",
                return_value={"ok": True, "artifact_path": str(root / "verify.txt")},
            ):
                summary = run_external_agent_live(
                    provider_name="claude",
                    arm_id="arm1_general_agent",
                    taskset_path=str(taskset),
                    out_dir=str(root / "out"),
                    budget_path=str(budget),
                    model_id="claude-opus-test",
                    model_id_resolvable=True,
                )
            self.assertEqual(summary["status"], "PASS")
            normalized = json.loads((root / "out" / "normalized_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized["provider_name"], "claude")
            self.assertEqual(normalized["summary"]["success_count"], 1)
            self.assertTrue((root / "out" / "tasks" / "t1" / "provider_mcp_config.json").exists())
            self.assertFalse((root / "out" / "tasks" / "t1" / "claude_mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
