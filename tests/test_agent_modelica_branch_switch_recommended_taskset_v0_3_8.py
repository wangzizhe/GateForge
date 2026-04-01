from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_recommended_taskset_v0_3_8 import build_branch_switch_recommended_taskset


class AgentModelicaV038BranchSwitchRecommendedTasksetTests(unittest.TestCase):
    def test_selects_only_explicit_branch_switch_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "keep_1",
                                "success_after_branch_switch": True,
                                "baseline_measurement_protocol": {"protocol_version": "v1"},
                            },
                            {"task_id": "drop_1", "success_after_branch_switch": False},
                            {"task_id": "keep_2", "success_after_branch_switch": True},
                            {"task_id": "keep_3", "success_after_branch_switch": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_branch_switch_recommended_taskset(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["task_ids"], ["keep_1", "keep_2", "keep_3"])


if __name__ == "__main__":
    unittest.main()
