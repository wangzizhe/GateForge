from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_12_block_b_runner import _build_run_summary, select_tasks


class AgentModelicaV0312BlockBRunnerTests(unittest.TestCase):
    def test_select_tasks_honors_task_ids_and_limit(self) -> None:
        tasks = [
            {"task_id": "a"},
            {"task_id": "b"},
            {"task_id": "c"},
        ]

        selected = select_tasks(tasks, task_ids=["b", "c"], task_limit=1)

        self.assertEqual([row["task_id"] for row in selected], ["b"])

    def test_build_run_summary_counts_passes_and_deterministic_only(self) -> None:
        payload = _build_run_summary(
            rows=[
                {"task_id": "a", "verdict": "PASS", "planner_invoked": True, "resolution_path": "llm_plan_followed"},
                {"task_id": "b", "verdict": "PASS", "planner_invoked": False, "resolution_path": "deterministic_rule_only"},
                {"task_id": "c", "verdict": "FAIL", "planner_invoked": False, "resolution_path": "unresolved"},
            ],
            planner_backend="gemini",
        )

        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["passed"], 2)
        self.assertEqual(payload["planner_invoked_count"], 1)
        self.assertEqual(payload["deterministic_only_count"], 1)
        self.assertEqual(payload["baseline_measurement_protocol"]["planner_backend"], "gemini")


if __name__ == "__main__":
    unittest.main()
