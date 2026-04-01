from __future__ import annotations

import unittest

from gateforge.agent_modelica_prompt_surface_v1 import (
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


if __name__ == "__main__":
    unittest.main()
