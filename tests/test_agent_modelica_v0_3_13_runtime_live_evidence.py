from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_13_runtime_live_evidence import (
    _build_run_summary,
    classify_progressive_solve,
    select_tasks,
)


class AgentModelicaV0313RuntimeLiveEvidenceTests(unittest.TestCase):
    def test_select_tasks_honors_ids_and_limit(self) -> None:
        tasks = [{"task_id": "a"}, {"task_id": "b"}, {"task_id": "c"}]
        selected = select_tasks(tasks, task_ids=["b", "c"], task_limit=1)
        self.assertEqual([row["task_id"] for row in selected], ["b"])

    def test_classify_progressive_solve_requires_pass_non_deterministic_and_progress(self) -> None:
        payload = classify_progressive_solve(
            {
                "executor_status": "PASS",
                "resolution_path": "rule_then_llm",
                "rounds_used": 3,
                "executor_runtime_hygiene": {"planner_event_count": 2},
                "attempts": [
                    {"check_model_pass": False, "simulate_pass": False},
                    {"check_model_pass": True, "simulate_pass": False},
                    {"check_model_pass": True, "simulate_pass": True},
                ],
            }
        )
        self.assertTrue(payload["progressive_solve"])
        self.assertIn("check_model_recovery", payload["progress_signal_labels"])
        self.assertIn("simulate_recovery", payload["progress_signal_labels"])

    def test_build_run_summary_counts_progressive_solves(self) -> None:
        summary = _build_run_summary(
            rows=[
                {
                    "task_id": "a",
                    "verdict": "PASS",
                    "planner_invoked": True,
                    "resolution_path": "rule_then_llm",
                    "rounds_used": 3,
                    "progressive_solve": True,
                    "v0_3_13_source_task_id": "seed_a",
                },
                {
                    "task_id": "b",
                    "verdict": "PASS",
                    "planner_invoked": False,
                    "resolution_path": "deterministic_rule_only",
                    "rounds_used": 1,
                    "progressive_solve": False,
                    "v0_3_13_source_task_id": "seed_b",
                },
                {
                    "task_id": "c",
                    "verdict": "FAIL",
                    "planner_invoked": False,
                    "resolution_path": "unresolved",
                    "rounds_used": 2,
                    "progressive_solve": False,
                    "v0_3_13_source_task_id": "seed_a",
                },
            ],
            planner_backend="gemini",
            taskset_path="runtime.json",
        )
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["multiround_success_count"], 1)
        self.assertEqual(summary["progressive_solve_count"], 1)
        self.assertEqual(summary["resolution_path_counts"]["rule_then_llm"], 1)
        self.assertEqual(summary["progressive_by_source_task_id"]["seed_a"], 1)

    def test_build_run_summary_falls_back_to_generic_source_id(self) -> None:
        summary = _build_run_summary(
            rows=[
                {
                    "task_id": "a",
                    "verdict": "PASS",
                    "planner_invoked": True,
                    "resolution_path": "rule_then_llm",
                    "rounds_used": 3,
                    "progressive_solve": True,
                    "v0_3_13_source_id": "init_pack_a",
                }
            ],
            planner_backend="gemini",
            taskset_path="runtime.json",
        )
        self.assertEqual(summary["progressive_by_source_task_id"]["init_pack_a"], 1)


if __name__ == "__main__":
    unittest.main()
