from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_replan_context_v1 import (
    AgentModelicaReplanContext,
    CandidateBranch,
    build_replan_context_dict,
)


class AgentModelicaReplanContextV1Tests(unittest.TestCase):
    def test_create_context_requires_structured_branch_candidates(self) -> None:
        payload = build_replan_context_dict(
            task_id="case_1",
            run_id="run_a",
            previous_successful_action="numeric_sweep:R_up",
            stall_signal="stalled_search_after_progress",
            current_branch="continue_current",
            candidate_branches=[
                CandidateBranch(
                    branch_id="switch_to_c",
                    branch_kind="parameter_branch",
                    trigger_signal="stalled_search_after_progress",
                    viability_status="candidate",
                    supporting_parameters=["C"],
                ),
                {
                    "branch_id": "switch_to_qin",
                    "branch_kind": "parameter_branch",
                    "trigger_signal": "stalled_search_after_progress",
                    "supporting_parameters": ["Qin"],
                },
            ],
            continue_current_branch=False,
            switch_branch=True,
            selected_branch="switch_to_c",
            replan_count=1,
            remaining_replan_budget=2,
            decision_reason_code="stall_then_branch_switch",
        )
        self.assertEqual(payload["schema_version"], "agent_modelica_replan_context_v1")
        self.assertEqual(len(payload["candidate_branches"]), 2)
        self.assertEqual(payload["candidate_branches"][0]["branch_id"], "switch_to_c")

    def test_switch_branch_requires_selected_branch(self) -> None:
        with self.assertRaises(ValueError):
            AgentModelicaReplanContext.create(
                task_id="case_1",
                run_id="run_a",
                previous_successful_action="numeric_sweep:R_up",
                stall_signal="stalled_search_after_progress",
                current_branch="continue_current",
                candidate_branches=[
                    {
                        "branch_id": "switch_to_c",
                        "branch_kind": "parameter_branch",
                        "trigger_signal": "stalled_search_after_progress",
                    }
                ],
                continue_current_branch=False,
                switch_branch=True,
                selected_branch="",
                replan_count=1,
                remaining_replan_budget=2,
                decision_reason_code="stall_then_branch_switch",
            )

    def test_context_can_be_written_to_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_replan_ctx_") as td:
            root = Path(td)
            path = root / "context.json"
            ctx = AgentModelicaReplanContext.create(
                task_id="case_2",
                run_id="run_b",
                previous_successful_action="numeric_sweep:C_up",
                stall_signal="stalled_search_after_progress",
                current_branch="continue_current",
                candidate_branches=[
                    {
                        "branch_id": "switch_to_R",
                        "branch_kind": "parameter_branch",
                        "trigger_signal": "stalled_search_after_progress",
                    }
                ],
                continue_current_branch=True,
                switch_branch=False,
                selected_branch="",
                replan_count=1,
                remaining_replan_budget=1,
                decision_reason_code="continue_once_before_switch",
            )
            ctx.write_json(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_id"], "case_2")
        self.assertEqual(payload["candidate_branches"][0]["branch_id"], "switch_to_R")


if __name__ == "__main__":
    unittest.main()
