from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_13_initialization_curriculum_taskset import (
    FAMILY_ID,
    build_initialization_curriculum_taskset,
)


class AgentModelicaV0313InitializationCurriculumTasksetTests(unittest.TestCase):
    def test_builds_expected_number_of_tasks(self) -> None:
        payload = build_initialization_curriculum_taskset(out_dir="/tmp/gf_v0313_init_taskset_test")
        self.assertEqual(payload["source_count"], 5)
        self.assertEqual(payload["task_count"], 10)
        self.assertEqual(payload["family_id"], FAMILY_ID)
        for row in payload["tasks"]:
            self.assertEqual(row["hidden_base_operator"], "init_equation_sign_flip")
            self.assertTrue(row["v0_3_13_initialization_target_lhs"])


if __name__ == "__main__":
    unittest.main()
