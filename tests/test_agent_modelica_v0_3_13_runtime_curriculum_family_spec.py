from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_runtime_curriculum_family_spec import build_family_summary_from_taskset
from gateforge.agent_modelica_v0_3_13_runtime_curriculum_taskset import FAMILY_ID


class AgentModelicaV0313RuntimeCurriculumFamilySpecTests(unittest.TestCase):
    def test_marks_curriculum_ready_at_eight_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            rows = []
            for idx in range(8):
                rows.append(
                    {
                        "task_id": f"case_{idx}",
                        "v0_3_13_family_id": FAMILY_ID,
                        "course_stage": "three_step_runtime_curriculum",
                        "hidden_base_operator": "paired_value_collapse",
                        "runtime_recovery_parameter_names": ["a", "b"],
                        "preview_contract": {
                            "preview_admission": True,
                            "residual_signal_cluster_id": "runtime_parameter_recovery",
                            "post_rule_residual_stage": "stage_5_runtime_numerical_instability",
                        },
                    }
                )
            taskset.write_text(json.dumps({"tasks": rows}), encoding="utf-8")

            payload = build_family_summary_from_taskset(
                candidate_taskset_path=str(taskset),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["lane_status"], "CURRICULUM_READY")
            self.assertEqual(payload["admitted_count"], 8)


if __name__ == "__main__":
    unittest.main()
