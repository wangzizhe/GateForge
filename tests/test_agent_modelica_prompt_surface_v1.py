from __future__ import annotations

import unittest

from gateforge.agent_modelica_prompt_surface_v1 import (
    build_branch_switch_replan_prompt,
    build_external_agent_probe_prompt,
    build_external_agent_repair_prompt,
)


class AgentModelicaPromptSurfaceV1Tests(unittest.TestCase):
    def test_build_external_agent_probe_prompt_mentions_tool(self) -> None:
        prompt = build_external_agent_probe_prompt(tool_name="omc_get_error_string")
        self.assertIn("shared OpenModelica MCP tool plane", prompt)
        self.assertIn("omc_get_error_string", prompt)

    def test_build_external_agent_repair_prompt_contains_budget_and_context(self) -> None:
        prompt = build_external_agent_repair_prompt(
            task_ctx={
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
        self.assertIn("max_omc_tool_calls: 6", prompt)
        self.assertIn("source_qualified_model_name: Buildings.Electrical.Examples.M", prompt)
        self.assertIn("Work in short iterations", prompt)

    def test_build_branch_switch_replan_prompt_includes_structured_branches(self) -> None:
        prompt = build_branch_switch_replan_prompt(
            task_ctx={
                "task_id": "t1",
                "failure_type": "simulate_error",
                "expected_stage": "simulate",
                "model_name": "M",
            },
            replan_ctx={
                "previous_successful_action": "increase_R",
                "stall_signal": "stalled_search_after_progress",
                "current_branch": "continue_on_R",
                "replan_count": 1,
                "remaining_replan_budget": 2,
                "candidate_branches": [
                    {
                        "branch_id": "continue_on_R",
                        "branch_kind": "continue_current_line",
                        "trigger_signal": "stalled_search_after_progress",
                        "supporting_parameters": ["R"],
                    },
                    {
                        "branch_id": "switch_to_C",
                        "branch_kind": "branch_switch_candidate",
                        "trigger_signal": "stalled_search_after_progress",
                        "supporting_parameters": ["C"],
                    },
                ],
            },
            budget={"max_replan_rounds": 2, "max_followup_actions": 3},
        )
        self.assertIn("candidate_branches_json", prompt)
        self.assertIn("\"branch_id\": \"switch_to_C\"", prompt)
        self.assertIn("Do not invent new branch ids", prompt)


if __name__ == "__main__":
    unittest.main()
