from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_curriculum_work_order import build_curriculum_work_order


class AgentModelicaV0313CurriculumWorkOrderTests(unittest.TestCase):
    def test_builds_include_and_exclude_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed = root / "seed.json"
            runtime = root / "runtime.json"
            preview = root / "preview.json"
            source = root / "source.json"
            seed.write_text(json.dumps({"lane_status": "SEED_READY", "admitted_count": 10}), encoding="utf-8")
            runtime.write_text(json.dumps({"lane_status": "CURRICULUM_READY", "admitted_count": 10}), encoding="utf-8")
            preview.write_text(
                json.dumps(
                    {
                        "rows": [
                            {"task_id": "a", "preview_reason": "post_rule_success_without_residual"},
                            {"task_id": "b", "preview_reason": "preview_admitted"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "a", "hidden_base_operator": "paired_value_bias_shift"},
                            {"task_id": "b", "hidden_base_operator": "paired_value_collapse"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = build_curriculum_work_order(
                seed_family_spec_path=str(seed),
                runtime_family_spec_path=str(runtime),
                preview_v036_path=str(preview),
                source_taskset_v036_path=str(source),
                out_dir=str(root / "out"),
            )

            self.assertEqual(len(payload["include_lanes"]), 2)
            exclude = payload["exclude_rules"][0]
            self.assertEqual(exclude["excluded_case_count"], 1)
            self.assertEqual(exclude["excluded_operator_counts"]["paired_value_bias_shift"], 1)


if __name__ == "__main__":
    unittest.main()
