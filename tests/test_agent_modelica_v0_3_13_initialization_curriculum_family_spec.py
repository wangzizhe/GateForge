from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_initialization_curriculum_family_spec import (
    build_family_summary_from_taskset,
)


class AgentModelicaV0313InitializationCurriculumFamilySpecTests(unittest.TestCase):
    def test_accepts_preview_admitted_initialization_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            tasks = []
            for idx in range(8):
                tasks.append(
                    {
                        "task_id": f"t{idx}",
                        "v0_3_13_family_id": "surface_cleanup_then_initialization_parameter_recovery",
                        "course_stage": "three_step_initialization_curriculum",
                        "hidden_base_operator": "init_equation_sign_flip",
                        "v0_3_13_initialization_target_lhs": "x",
                        "preview_contract": {
                            "preview_admission": True,
                            "residual_signal_cluster_id": "initialization_parameter_recovery",
                            "post_rule_residual_stage": "stage_4_initialization_singularity",
                        },
                    }
                )
            taskset.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
            payload = build_family_summary_from_taskset(
                candidate_taskset_path=str(taskset),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["lane_status"], "CURRICULUM_READY")
            self.assertEqual(payload["admitted_count"], 8)


if __name__ == "__main__":
    unittest.main()
