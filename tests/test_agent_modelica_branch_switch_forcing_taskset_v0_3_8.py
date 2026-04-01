from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_forcing_taskset_v0_3_8 import (
    build_branch_switch_forcing_taskset,
)


class BranchSwitchForcingTasksetV038Tests(unittest.TestCase):
    def test_build_taskset_converts_v037_branch_switch_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.json"
            source.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "demo",
                                "hidden_base_operator": "paired_value_collapse",
                                "candidate_branches": [
                                    {
                                        "branch_id": "continue_on_r",
                                        "branch_kind": "continue_current_line",
                                        "trigger_signal": "stalled_search_after_progress",
                                    },
                                    {
                                        "branch_id": "switch_to_c",
                                        "branch_kind": "branch_switch_candidate",
                                        "trigger_signal": "stalled_search_after_progress",
                                    },
                                ],
                                "current_branch": "continue_on_r",
                                "preferred_branch": "switch_to_c",
                                "branch_switch_design": {
                                    "current_branch_param": "R",
                                    "preferred_branch_param": "C",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = Path(td) / "out"
            payload = build_branch_switch_forcing_taskset(
                source_taskset_path=str(source),
                out_dir=str(out_dir),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["task_count"], 1)
            task = payload["tasks"][0]
            self.assertEqual(task["branch_forcing_design"]["success_mode_target"], "success_after_branch_switch")


if __name__ == "__main__":
    unittest.main()
