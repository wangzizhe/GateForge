from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_post_restore_taskset_v0_3_6 import (
    build_post_restore_taskset,
)


class AgentModelicaPostRestoreTasksetV036Tests(unittest.TestCase):
    def test_build_post_restore_taskset_writes_ten_tasks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_taskset_") as td:
            payload = build_post_restore_taskset(out_dir=td)
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["task_count"], 10)
            self.assertEqual(payload["family_id"], "post_restore_residual_semantic_conflict")
            self.assertIn("paired_value_collapse", payload["operators_used"])
            self.assertIn("paired_value_bias_shift", payload["operators_used"])
            taskset_path = Path(td) / "taskset.json"
            self.assertTrue(taskset_path.exists())
            tasks_dir = Path(td) / "tasks"
            self.assertEqual(len(list(tasks_dir.glob("*.json"))), 10)

    def test_generated_tasks_carry_v036_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_taskset_fields_") as td:
            payload = build_post_restore_taskset(out_dir=td)
            task = payload["tasks"][0]
            self.assertEqual(task["v0_3_6_family_id"], "post_restore_residual_semantic_conflict")
            self.assertTrue(task["multi_parameter_hidden_base"])
            self.assertTrue(task["baseline_expectation"]["single_sweep_expected_to_fail"])


if __name__ == "__main__":
    unittest.main()
