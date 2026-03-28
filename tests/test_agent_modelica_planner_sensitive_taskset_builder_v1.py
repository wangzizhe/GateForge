import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_planner_sensitive_taskset_builder_v1 import build_planner_sensitive_taskset


class AgentModelicaPlannerSensitiveTasksetBuilderV1Tests(unittest.TestCase):
    def test_build_planner_sensitive_taskset_selects_llm_invoked_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            results = root / "results.json"
            taskset = root / "taskset.json"
            out_taskset = root / "out_taskset.json"
            results.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "t1", "failure_type": "stability_then_behavior", "llm_request_count_delta": 1, "llm_plan_used": True, "passed": True, "rounds_used": 2},
                            {"task_id": "t2", "failure_type": "behavior_then_robustness", "llm_request_count_delta": 2, "llm_plan_generated": True, "passed": True, "rounds_used": 3},
                            {"task_id": "t3", "failure_type": "simulate_error", "llm_request_count_delta": 0, "passed": True, "rounds_used": 1},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "failure_type": "stability_then_behavior"},
                            {"task_id": "t2", "failure_type": "behavior_then_robustness"},
                            {"task_id": "t3", "failure_type": "simulate_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = build_planner_sensitive_taskset(
                results_paths=[str(results)],
                taskset_paths=[str(taskset)],
                out_taskset_path=str(out_taskset),
                max_tasks=10,
            )
            out_payload = json.loads(out_taskset.read_text(encoding="utf-8"))
            selected_ids = [row["task_id"] for row in out_payload.get("tasks") or []]
            self.assertEqual(selected_ids, ["t2", "t1"])
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(Path(summary["layer_sidecar_path"]).exists())
            self.assertEqual(summary["layer_sidecar_summary"]["inferred_count"], 2)

    def test_build_planner_sensitive_taskset_marks_empty_selection_as_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            results = root / "results.json"
            taskset = root / "taskset.json"
            out_taskset = root / "out_taskset.json"
            results.write_text(json.dumps({"records": [{"task_id": "t1", "llm_request_count_delta": 0, "passed": True}]}), encoding="utf-8")
            taskset.write_text(json.dumps({"tasks": [{"task_id": "t1"}]}), encoding="utf-8")
            summary = build_planner_sensitive_taskset(
                results_paths=[str(results)],
                taskset_paths=[str(taskset)],
                out_taskset_path=str(out_taskset),
            )
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["validation_reason"], "no_planner_sensitive_tasks")


if __name__ == "__main__":
    unittest.main()
