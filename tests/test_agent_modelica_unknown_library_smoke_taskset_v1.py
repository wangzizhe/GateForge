import unittest

from gateforge.agent_modelica_unknown_library_smoke_taskset_v1 import build_smoke_taskset


class AgentModelicaUnknownLibrarySmokeTasksetV1Tests(unittest.TestCase):
    def test_build_smoke_taskset_selects_requested_tasks_in_order(self) -> None:
        payload = {
            "tasks": [
                {"task_id": "t2", "source_meta": {"library_id": "libb"}},
                {"task_id": "t1", "source_meta": {"library_id": "liba"}},
                {"task_id": "t3", "source_meta": {"library_id": "libc"}},
            ]
        }
        taskset, summary = build_smoke_taskset(payload=payload, requested_task_ids=["t1", "t3"])
        self.assertEqual([row["task_id"] for row in taskset["tasks"]], ["t1", "t3"])
        self.assertEqual(summary.get("counts_by_library"), {"liba": 1, "libc": 1})
        self.assertEqual(summary.get("status"), "PASS")

    def test_build_smoke_taskset_fails_when_task_missing(self) -> None:
        payload = {"tasks": [{"task_id": "t1", "source_meta": {"library_id": "liba"}}]}
        _taskset, summary = build_smoke_taskset(payload=payload, requested_task_ids=["t1", "t2"])
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertIn("missing_task_id:t2", summary.get("reasons") or [])


if __name__ == "__main__":
    unittest.main()
