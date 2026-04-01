from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_6_recommended_taskset import (
    build_recommended_taskset,
)


class AgentModelicaV036RecommendedTasksetTests(unittest.TestCase):
    def test_filters_tasks_to_recommended_operator(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_recommended_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            analysis = root / "analysis.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "a", "hidden_base_operator": "paired_value_collapse"},
                            {"task_id": "b", "hidden_base_operator": "paired_value_collapse"},
                            {"task_id": "c", "hidden_base_operator": "paired_value_bias_shift"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            analysis.write_text(
                json.dumps({"recommended_operator": "paired_value_collapse"}),
                encoding="utf-8",
            )
            payload = build_recommended_taskset(
                refreshed_summary_path=str(refreshed),
                operator_analysis_summary_path=str(analysis),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["task_count"], 2)
            self.assertEqual(payload["task_ids"], ["a", "b"])
            self.assertTrue((root / "out" / "taskset.json").exists())


if __name__ == "__main__":
    unittest.main()
