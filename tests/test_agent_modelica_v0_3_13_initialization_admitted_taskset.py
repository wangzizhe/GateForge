from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_initialization_admitted_taskset import (
    build_initialization_admitted_taskset,
)


class AgentModelicaV0313InitializationAdmittedTasksetTests(unittest.TestCase):
    def test_keeps_only_preview_admitted_initialization_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            taskset = root / "taskset.json"
            preview = root / "preview.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "keep", "hidden_base_operator": "init_equation_sign_flip"},
                            {"task_id": "drop", "hidden_base_operator": "init_equation_sign_flip"},
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
                                "task_id": "keep",
                                "preview_admission": True,
                                "residual_signal_cluster_id": "initialization_parameter_recovery",
                                "surface_fixable_by_rule": True,
                                "surface_rule_id": "rule_simulate_error_injection_repair",
                                "post_rule_residual_stage": "stage_4_initialization_singularity",
                            },
                            {
                                "task_id": "drop",
                                "preview_admission": False,
                                "residual_signal_cluster_id": "initialization_parameter_recovery",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_initialization_admitted_taskset(
                source_taskset_path=str(taskset),
                preview_summary_path=str(preview),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["task_count"], 1)
            self.assertEqual(payload["task_ids"], ["keep"])


if __name__ == "__main__":
    unittest.main()
