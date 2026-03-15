import unittest

from gateforge.agent_modelica_unknown_library_smoke3_summary_v1 import build_smoke_summary


class AgentModelicaUnknownLibrarySmoke3SummaryV1Tests(unittest.TestCase):
    def test_build_smoke_summary_passes_when_three_records_complete(self) -> None:
        taskset = {
            "tasks": [
                {"task_id": "t1", "source_meta": {"library_id": "liba"}},
                {"task_id": "t2", "source_meta": {"library_id": "libb"}},
                {"task_id": "t3", "source_meta": {"library_id": "libc"}},
            ]
        }
        results = {
            "records": [
                {"task_id": "t1", "passed": True, "error_message": "", "stderr_snippet": "", "attempts": [{}], "elapsed_sec": 12.0},
                {"task_id": "t2", "passed": True, "error_message": "", "stderr_snippet": "", "attempts": [{}], "elapsed_sec": 18.0},
                {"task_id": "t3", "passed": False, "error_message": "connector mismatch", "stderr_snippet": "Error", "attempts": [{}], "elapsed_sec": 40.0},
            ]
        }
        summary = build_smoke_summary(
            taskset_payload=taskset,
            results_payload=results,
            records_payload=[],
            per_task_time_budget_sec=300.0,
            min_tasks_within_budget=2,
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(summary.get("completed_records"), 3)
        self.assertTrue(bool(summary.get("tasks_within_time_budget_ok")))

    def test_build_smoke_summary_needs_review_when_records_incomplete(self) -> None:
        taskset = {
            "tasks": [
                {"task_id": "t1", "source_meta": {"library_id": "liba"}},
                {"task_id": "t2", "source_meta": {"library_id": "libb"}},
                {"task_id": "t3", "source_meta": {"library_id": "libc"}},
            ]
        }
        results = {
            "records": [
                {"task_id": "t1", "passed": True, "error_message": "", "stderr_snippet": "", "attempts": [{}], "elapsed_sec": 12.0},
                {"task_id": "t2", "passed": False, "error_message": "", "stderr_snippet": "", "attempts": [], "elapsed_sec": 500.0},
            ]
        }
        summary = build_smoke_summary(
            taskset_payload=taskset,
            results_payload=results,
            records_payload=[],
            per_task_time_budget_sec=300.0,
            min_tasks_within_budget=2,
        )
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertIn("incomplete_records:2/3", summary.get("reasons") or [])


if __name__ == "__main__":
    unittest.main()
