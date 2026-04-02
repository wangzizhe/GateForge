from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_seed_family_spec import build_family_summary_from_taskset
from gateforge.agent_modelica_v0_3_13_seed_taskset import FAMILY_INITIALIZATION, FAMILY_RUNTIME


class AgentModelicaV0313SeedFamilySpecTests(unittest.TestCase):
    def test_marks_seed_ready_when_both_families_clear_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            rows = []
            for idx in range(5):
                rows.append(
                    {
                        "task_id": f"runtime_{idx}",
                        "v0_3_13_family_id": FAMILY_RUNTIME,
                        "course_stage": "two_step_residual",
                        "resolution_path": "rule_then_llm",
                        "rounds_used": 3,
                        "preview_contract": {
                            "surface_fixable_by_rule": True,
                            "preview_admission": True,
                            "post_rule_residual_stage": "stage_5_runtime_numerical_instability",
                        },
                    }
                )
            for idx in range(3):
                rows.append(
                    {
                        "task_id": f"init_{idx}",
                        "v0_3_13_family_id": FAMILY_INITIALIZATION,
                        "course_stage": "two_step_residual",
                        "resolution_path": "rule_then_llm",
                        "rounds_used": 3,
                        "preview_contract": {
                            "surface_fixable_by_rule": True,
                            "preview_admission": True,
                            "post_rule_residual_stage": "stage_4_initialization_singularity",
                        },
                    }
                )
            taskset.write_text(json.dumps({"tasks": rows}), encoding="utf-8")

            payload = build_family_summary_from_taskset(
                candidate_taskset_path=str(taskset),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["lane_status"], "SEED_READY")
            self.assertEqual(payload["admitted_count"], 8)


if __name__ == "__main__":
    unittest.main()
