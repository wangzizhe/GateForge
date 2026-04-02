from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_runtime_expansion_work_order import (
    build_runtime_expansion_work_order,
)


class AgentModelicaV0313RuntimeExpansionWorkOrderTests(unittest.TestCase):
    def test_summarizes_admitted_and_rejected_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            preview = root / "preview.json"
            taskset = root / "taskset.json"
            family = root / "family.json"
            preview.write_text(
                json.dumps(
                    {
                        "rows": [
                            {"task_id": "a", "preview_reason": "preview_admitted"},
                            {"task_id": "b", "preview_reason": "post_rule_success_without_residual", "post_rule_residual_reason": ""},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "a", "v0_3_13_source_task_id": "seed_a"},
                            {"task_id": "c", "v0_3_13_source_task_id": "seed_a"},
                            {"task_id": "d", "v0_3_13_source_task_id": "seed_b"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            family.write_text(json.dumps({"lane_status": "CURRICULUM_READY", "admitted_count": 3}), encoding="utf-8")

            payload = build_runtime_expansion_work_order(
                preview_summary_path=str(preview),
                expansion_taskset_path=str(taskset),
                expansion_family_spec_path=str(family),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["lane_status"], "CURRICULUM_READY")
            self.assertEqual(payload["admitted_count"], 3)
            self.assertEqual(payload["rejected_count"], 1)
            self.assertEqual(payload["admitted_by_source_task_id"]["seed_a"], 2)


if __name__ == "__main__":
    unittest.main()
