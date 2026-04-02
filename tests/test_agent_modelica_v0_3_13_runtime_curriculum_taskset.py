from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_runtime_curriculum_taskset import (
    FAMILY_ID,
    build_runtime_curriculum_taskset,
)


class AgentModelicaV0313RuntimeCurriculumTasksetTests(unittest.TestCase):
    def test_selects_only_runtime_preview_admitted_collapse_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            preview = root / "preview.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "keep_me",
                                "hidden_base_operator": "paired_value_collapse",
                                "mutation_spec": {
                                    "hidden_base": {
                                        "audit": {
                                            "mutations": [
                                                {"param_name": "a"},
                                                {"param_name": "b"},
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "task_id": "drop_me",
                                "hidden_base_operator": "paired_value_bias_shift",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "keep_me",
                                "preview_admission": True,
                                "residual_signal_cluster_id": "runtime_parameter_recovery",
                                "surface_fixable_by_rule": True,
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "post_rule_residual_stage": "stage_5_runtime_numerical_instability",
                                "post_rule_residual_error_type": "numerical_instability",
                                "post_rule_residual_reason": "division by zero",
                            },
                            {
                                "task_id": "drop_me",
                                "preview_admission": True,
                                "residual_signal_cluster_id": "runtime_parameter_recovery",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = build_runtime_curriculum_taskset(
                source_taskset_path=str(taskset),
                preview_summary_path=str(preview),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["task_count"], 1)
            self.assertEqual(payload["tasks"][0]["v0_3_13_family_id"], FAMILY_ID)


if __name__ == "__main__":
    unittest.main()
